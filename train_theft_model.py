"""
Training Script for Theft Detection ML Model
Retrains Random Forest model with real labeled data

Usage:
    python train_theft_model.py --data labeled_thefts.csv --output models/theft_detection_rf.pkl

Author: Fuel Copilot Team
Version: 1.0.0
Date: December 23, 2025
"""

import argparse
import logging
from pathlib import Path
from typing import List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import cross_val_score, train_test_split

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_labeled_data(csv_path: str) -> pd.DataFrame:
    """
    Load labeled theft data from CSV.
    
    Expected CSV format:
    truck_id,timestamp,fuel_drop_pct,speed,latitude,longitude,hour_of_day,is_weekend,sensor_drift,is_theft
    DO9693,2025-12-01 02:30:00,15.2,0,40.712,-74.006,2,0,2.3,1
    
    Columns:
    - truck_id: Truck identifier
    - timestamp: Event timestamp
    - fuel_drop_pct: Fuel level drop percentage
    - speed: Speed at time of drop (mph)
    - latitude: GPS latitude
    - longitude: GPS longitude
    - hour_of_day: Hour (0-23)
    - is_weekend: 1 if weekend, 0 if weekday
    - sensor_drift: Absolute drift percentage
    - is_theft: LABEL - 1 if confirmed theft, 0 if normal
    """
    df = pd.read_csv(csv_path)
    
    # Validate required columns
    required_cols = [
        'fuel_drop_pct', 'speed', 'latitude', 'longitude',
        'hour_of_day', 'is_weekend', 'sensor_drift', 'is_theft'
    ]
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")
    
    logger.info(f"Loaded {len(df)} labeled events from {csv_path}")
    logger.info(f"  - Thefts: {df['is_theft'].sum()}")
    logger.info(f"  - Normal: {(~df['is_theft'].astype(bool)).sum()}")
    
    return df


def prepare_features(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """
    Prepare feature matrix X and labels y.
    
    Features (8 total):
    1. fuel_drop_pct
    2. speed
    3. is_moving (derived from speed)
    4. latitude
    5. longitude
    6. hour_of_day
    7. is_weekend
    8. sensor_drift
    """
    # Feature engineering
    df['is_moving'] = (df['speed'] > 5).astype(int)
    
    feature_cols = [
        'fuel_drop_pct',
        'speed', 
        'is_moving',
        'latitude',
        'longitude',
        'hour_of_day',
        'is_weekend',
        'sensor_drift'
    ]
    
    X = df[feature_cols].values
    y = df['is_theft'].values
    
    return X, y


def train_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    n_estimators: int = 100,
    max_depth: int = 10,
    random_state: int = 42
) -> RandomForestClassifier:
    """
    Train Random Forest classifier.
    
    Args:
        X_train: Training features
        y_train: Training labels
        n_estimators: Number of trees in forest
        max_depth: Maximum tree depth
        random_state: Random seed for reproducibility
        
    Returns:
        Trained RandomForestClassifier
    """
    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight='balanced',  # Handle class imbalance
        random_state=random_state,
        n_jobs=-1  # Use all CPU cores
    )
    
    logger.info("Training Random Forest model...")
    clf.fit(X_train, y_train)
    
    # Feature importance
    feature_names = [
        'fuel_drop_pct', 'speed', 'is_moving', 
        'latitude', 'longitude', 'hour_of_day', 
        'is_weekend', 'sensor_drift'
    ]
    importance = sorted(
        zip(feature_names, clf.feature_importances_),
        key=lambda x: x[1],
        reverse=True
    )
    
    logger.info("\nFeature Importance:")
    for feat, imp in importance:
        logger.info(f"  {feat}: {imp:.4f}")
    
    return clf


def evaluate_model(
    clf: RandomForestClassifier,
    X_test: np.ndarray,
    y_test: np.ndarray
) -> dict:
    """
    Evaluate model performance on test set.
    
    Returns:
        Dictionary with metrics
    """
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]
    
    metrics = {
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred),
        'recall': recall_score(y_test, y_pred),
        'f1_score': f1_score(y_test, y_pred),
    }
    
    logger.info("\nTest Set Performance:")
    logger.info(f"  Accuracy:  {metrics['accuracy']:.4f}")
    logger.info(f"  Precision: {metrics['precision']:.4f}")
    logger.info(f"  Recall:    {metrics['recall']:.4f}")
    logger.info(f"  F1 Score:  {metrics['f1_score']:.4f}")
    
    logger.info("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    logger.info(f"  TN: {cm[0,0]}  FP: {cm[0,1]}")
    logger.info(f"  FN: {cm[1,0]}  TP: {cm[1,1]}")
    
    logger.info("\nClassification Report:")
    logger.info("\n" + classification_report(y_test, y_pred, target_names=['Normal', 'Theft']))
    
    return metrics


def cross_validate(
    clf: RandomForestClassifier,
    X: np.ndarray,
    y: np.ndarray,
    cv: int = 5
) -> dict:
    """
    Perform k-fold cross-validation.
    
    Returns:
        Dictionary with CV scores
    """
    logger.info(f"\nPerforming {cv}-fold cross-validation...")
    
    cv_scores = cross_val_score(clf, X, y, cv=cv, scoring='f1')
    
    logger.info(f"  CV F1 Scores: {cv_scores}")
    logger.info(f"  Mean F1: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
    
    return {
        'cv_scores': cv_scores,
        'mean_f1': cv_scores.mean(),
        'std_f1': cv_scores.std()
    }


def main():
    parser = argparse.ArgumentParser(description='Train Theft Detection ML Model')
    parser.add_argument(
        '--data',
        type=str,
        required=True,
        help='Path to labeled CSV data (see docstring for format)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='models/theft_detection_rf.pkl',
        help='Output path for trained model'
    )
    parser.add_argument(
        '--test-size',
        type=float,
        default=0.2,
        help='Proportion of data for test set (default: 0.2)'
    )
    parser.add_argument(
        '--n-estimators',
        type=int,
        default=100,
        help='Number of trees in Random Forest (default: 100)'
    )
    parser.add_argument(
        '--max-depth',
        type=int,
        default=10,
        help='Maximum tree depth (default: 10)'
    )
    parser.add_argument(
        '--cv',
        type=int,
        default=5,
        help='Number of cross-validation folds (default: 5)'
    )
    
    args = parser.parse_args()
    
    # Load data
    df = load_labeled_data(args.data)
    
    # Prepare features
    X, y = prepare_features(df)
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=42, stratify=y
    )
    
    logger.info(f"\nDataset split:")
    logger.info(f"  Training:   {len(X_train)} samples")
    logger.info(f"  Test:       {len(X_test)} samples")
    
    # Train model
    clf = train_model(
        X_train, y_train,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth
    )
    
    # Cross-validation
    cv_results = cross_validate(clf, X_train, y_train, cv=args.cv)
    
    # Evaluate on test set
    test_metrics = evaluate_model(clf, X_test, y_test)
    
    # Save model
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    joblib.dump(clf, output_path)
    logger.info(f"\n✅ Model saved to {output_path}")
    
    # Save metadata
    metadata = {
        'training_date': pd.Timestamp.now().isoformat(),
        'training_samples': len(X_train),
        'test_samples': len(X_test),
        'n_estimators': args.n_estimators,
        'max_depth': args.max_depth,
        'test_accuracy': test_metrics['accuracy'],
        'test_f1': test_metrics['f1_score'],
        'cv_mean_f1': cv_results['mean_f1'],
        'cv_std_f1': cv_results['std_f1'],
    }
    
    metadata_path = output_path.with_suffix('.json')
    import json
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"📊 Metadata saved to {metadata_path}")
    
    logger.info("\n" + "="*60)
    logger.info("TRAINING COMPLETE")
    logger.info("="*60)
    logger.info(f"Model:     {output_path}")
    logger.info(f"Accuracy:  {test_metrics['accuracy']:.2%}")
    logger.info(f"F1 Score:  {test_metrics['f1_score']:.4f}")
    logger.info(f"CV F1:     {cv_results['mean_f1']:.4f} ± {cv_results['std_f1']:.4f}")
    logger.info("="*60)


if __name__ == '__main__':
    main()
