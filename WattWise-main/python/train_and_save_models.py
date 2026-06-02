#!/usr/bin/env python3
"""
Train and Save Energy Prediction Models
This script trains both regression and classification models and saves them for use in the VS Code extension
"""

import pandas as pd
import numpy as np
import joblib
import json
import os
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler, LabelEncoder
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier
from sklearn.pipeline import Pipeline

# Import XGBoost if available
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("Warning: XGBoost not available, will use GradientBoosting for classification")

def load_and_prepare_data():
    """Load and prepare the training data"""
    print("Loading training data...")

    # Load data
    X_train = pd.read_csv('../data/X_train_base_features.csv', index_col=0)
    X_test = pd.read_csv('../data/X_test_base_features.csv', index_col=0)
    targets_df = pd.read_csv('../data/target_variables.csv', index_col=0)

    y_train = targets_df.loc[X_train.index, 'energy_train']
    y_test = targets_df.loc[X_test.index, 'energy_test']

    print(f"Loaded - Train: {len(X_train)}, Test: {len(X_test)}")
    print(f"Energy range - Train: {y_train.min():.2e} to {y_train.max():.2e}")

    # Apply outlier removal (88% percentile as per optimal settings)
    percentile = 100  # Use 100 to keep all data as in the original code
    lower_threshold = (100 - percentile) / 2
    upper_threshold = percentile + (100 - percentile) / 2

    lower_bound = np.percentile(y_train, lower_threshold)
    upper_bound = np.percentile(y_train, upper_threshold)

    train_mask = (y_train >= lower_bound) & (y_train <= upper_bound)
    test_mask = (y_test >= lower_bound) & (y_test <= upper_bound)

    X_train_clean = X_train[train_mask].copy()
    y_train_clean = y_train[train_mask].copy()
    X_test_clean = X_test[test_mask].copy()
    y_test_clean = y_test[test_mask].copy()

    print(f"After outlier removal - Train: {len(X_train_clean)}, Test: {len(X_test_clean)}")

    return X_train_clean, y_train_clean, X_test_clean, y_test_clean

def create_feature_preprocessor(X_train):
    """Create optimal feature preprocessing pipeline"""
    feature_groups = {
        'standard_features': [],
        'robust_features': [],
        'minmax_features': [],
        'binary_features': []
    }

    for feature in X_train.columns:
        if feature.startswith('inv_'):
            feature_groups['minmax_features'].append(feature)
        elif any(pattern in feature for pattern in ['_squared', '_x_', '_div_']):
            feature_groups['robust_features'].append(feature)
        elif feature.startswith('block_') and '_x_' not in feature:
            feature_groups['binary_features'].append(feature)
        else:
            feature_groups['standard_features'].append(feature)

    transformers = []
    if feature_groups['standard_features']:
        transformers.append(('standard', StandardScaler(), feature_groups['standard_features']))
    if feature_groups['robust_features']:
        transformers.append(('robust', RobustScaler(), feature_groups['robust_features']))
    if feature_groups['minmax_features']:
        transformers.append(('minmax', MinMaxScaler(), feature_groups['minmax_features']))
    if feature_groups['binary_features']:
        transformers.append(('binary', 'passthrough', feature_groups['binary_features']))

    return ColumnTransformer(transformers=transformers, remainder='drop')

def train_regression_model(X_train, y_train, X_test, y_test, preprocessor):
    """Train Gradient Boosting regression model"""
    print("\n" + "="*60)
    print("Training Regression Model (Gradient Boosting)")
    print("="*60)

    # Apply sqrt transformation (optimal from experiments)
    y_train_transformed = np.sqrt(y_train)
    y_test_transformed = np.sqrt(y_test)

    # Create the optimal Gradient Boosting model
    model = GradientBoostingRegressor(
        n_estimators=250,
        max_depth=6,
        learning_rate=0.06,
        subsample=0.85,
        min_samples_split=20,
        min_samples_leaf=8,
        max_features='sqrt',
        random_state=42
    )

    # Create pipeline
    pipeline = Pipeline([
        ('preprocessor', preprocessor),
        ('model', model)
    ])

    # Train
    print("Training...")
    pipeline.fit(X_train, y_train_transformed)

    # Evaluate
    train_score = pipeline.score(X_train, y_train_transformed)
    test_score = pipeline.score(X_test, y_test_transformed)

    print(f"Training R²: {train_score:.4f}")
    print(f"Test R²: {test_score:.4f}")
    print(f"Overfitting Gap: {train_score - test_score:.4f}")

    return pipeline, {'train_r2': train_score, 'test_r2': test_score}

def create_energy_categories(y_train, y_test):
    """Create Low/Medium/High categories using quantiles"""
    print("\nCreating energy categories...")

    # Use training data to define boundaries
    q33 = np.quantile(y_train, 0.33)
    q67 = np.quantile(y_train, 0.67)

    print(f"  Low: ≤ {q33:.2e}")
    print(f"  Medium: {q33:.2e} to {q67:.2e}")
    print(f"  High: > {q67:.2e}")

    # Apply to both sets
    y_train_cat = pd.cut(y_train, bins=[0, q33, q67, float('inf')],
                         labels=['Low', 'Medium', 'High'], include_lowest=True)
    y_test_cat = pd.cut(y_test, bins=[0, q33, q67, float('inf')],
                        labels=['Low', 'Medium', 'High'], include_lowest=True)

    # Return both categories and boundaries
    boundaries = {'q33': q33, 'q67': q67}

    return y_train_cat, y_test_cat, boundaries

def train_classification_model(X_train, y_train_cat, X_test, y_test_cat, preprocessor):
    """Train XGBoost classification model"""
    print("\n" + "="*60)
    print("Training Classification Model (XGBoost)")
    print("="*60)

    # Encode labels
    label_encoder = LabelEncoder()
    y_train_encoded = label_encoder.fit_transform(y_train_cat)
    y_test_encoded = label_encoder.transform(y_test_cat)

    print(f"Classes: {label_encoder.classes_}")

    # Create the optimal XGBoost model
    if XGBOOST_AVAILABLE:
        model = xgb.XGBClassifier(
            n_estimators=250,
            max_depth=6,
            learning_rate=0.08,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_alpha=0.3,
            reg_lambda=0.3,
            min_child_weight=5,
            random_state=42,
            eval_metric='mlogloss',
            n_jobs=-1
        )
    else:
        # Fallback to Gradient Boosting
        model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.08,
            subsample=0.85,
            min_samples_split=25,
            min_samples_leaf=15,
            max_features='sqrt',
            random_state=42
        )

    # Create pipeline
    pipeline = Pipeline([
        ('preprocessor', preprocessor),
        ('model', model)
    ])

    # Train
    print("Training...")
    pipeline.fit(X_train, y_train_encoded)

    # Evaluate
    from sklearn.metrics import accuracy_score, f1_score
    train_pred = pipeline.predict(X_train)
    test_pred = pipeline.predict(X_test)

    train_acc = accuracy_score(y_train_encoded, train_pred)
    test_acc = accuracy_score(y_test_encoded, test_pred)
    test_f1 = f1_score(y_test_encoded, test_pred, average='weighted')

    print(f"Training Accuracy: {train_acc:.4f}")
    print(f"Test Accuracy: {test_acc:.4f}")
    print(f"Test F1 Score: {test_f1:.4f}")
    print(f"Overfitting Gap: {train_acc - test_acc:.4f}")

    return pipeline, label_encoder, {
        'train_acc': train_acc,
        'test_acc': test_acc,
        'test_f1': test_f1
    }

def save_models(regression_pipeline, classification_pipeline, label_encoder,
                feature_names, energy_boundaries, regression_metrics, classification_metrics):
    """Save all models and metadata"""
    print("\n" + "="*60)
    print("Saving Models and Metadata")
    print("="*60)

    models_dir = Path('models')
    models_dir.mkdir(exist_ok=True)

    # Save regression model
    reg_path = models_dir / 'gradient_boosting_regressor.joblib'
    joblib.dump(regression_pipeline, reg_path)
    print(f"✓ Saved regression model: {reg_path}")

    # Save classification model
    clf_path = models_dir / 'xgboost_classifier.joblib'
    joblib.dump(classification_pipeline, clf_path)
    print(f"✓ Saved classification model: {clf_path}")

    # Save label encoder
    encoder_path = models_dir / 'label_encoder.joblib'
    joblib.dump(label_encoder, encoder_path)
    print(f"✓ Saved label encoder: {encoder_path}")

    # Save metadata
    metadata = {
        'feature_names': list(feature_names),
        'n_features': len(feature_names),
        'energy_boundaries': energy_boundaries,
        'class_labels': list(label_encoder.classes_),
        'regression_metrics': regression_metrics,
        'classification_metrics': classification_metrics,
        'regression_uses_sqrt_transform': True,
        'model_info': {
            'regression': 'GradientBoostingRegressor',
            'classification': 'XGBoostClassifier' if XGBOOST_AVAILABLE else 'GradientBoostingClassifier'
        }
    }

    metadata_path = models_dir / 'model_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Saved metadata: {metadata_path}")

    print("\n✅ All models and metadata saved successfully!")
    print(f"\nModel Performance Summary:")
    print(f"  Regression - Test R²: {regression_metrics['test_r2']:.4f}")
    print(f"  Classification - Test Accuracy: {classification_metrics['test_acc']:.4f}")

def main():
    """Main training pipeline"""
    print("="*60)
    print("ENERGY PREDICTION MODEL TRAINING")
    print("="*60)

    # Load data
    X_train, y_train, X_test, y_test = load_and_prepare_data()

    # Create preprocessor
    preprocessor = create_feature_preprocessor(X_train)

    # Save feature names
    feature_names = X_train.columns.tolist()
    print(f"\nTotal features: {len(feature_names)}")

    # Train regression model
    regression_pipeline, regression_metrics = train_regression_model(
        X_train, y_train, X_test, y_test, preprocessor
    )

    # Create energy categories
    y_train_cat, y_test_cat, energy_boundaries = create_energy_categories(y_train, y_test)

    # Train classification model (need new preprocessor for classification)
    classification_preprocessor = create_feature_preprocessor(X_train)
    classification_pipeline, label_encoder, classification_metrics = train_classification_model(
        X_train, y_train_cat, X_test, y_test_cat, classification_preprocessor
    )

    # Save everything
    save_models(
        regression_pipeline,
        classification_pipeline,
        label_encoder,
        feature_names,
        energy_boundaries,
        regression_metrics,
        classification_metrics
    )

    print("\n" + "="*60)
    print("TRAINING COMPLETE!")
    print("="*60)
    print("\nYou can now use these models in the VS Code extension.")

if __name__ == "__main__":
    main()
