#!/usr/bin/env python3
"""
Load trained models and predict energy consumption for code blocks
Accepts features via stdin as JSON and outputs predictions
"""

import json
import sys
import numpy as np
import pandas as pd
import joblib
from pathlib import Path


class EnergyPredictor:
    """Load models and make predictions"""

    def __init__(self, models_dir='models'):
        self.models_dir = Path(models_dir)
        self.regression_model = None
        self.classification_model = None
        self.label_encoder = None
        self.metadata = None
        self.load_models()

    def load_models(self):
        """Load all saved models and metadata"""
        try:
            # Load metadata
            metadata_path = self.models_dir / 'model_metadata.json'
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)

            # Load regression model
            reg_path = self.models_dir / 'gradient_boosting_regressor.joblib'
            self.regression_model = joblib.load(reg_path)

            # Load classification model
            clf_path = self.models_dir / 'xgboost_classifier.joblib'
            self.classification_model = joblib.load(clf_path)

            # Load label encoder
            encoder_path = self.models_dir / 'label_encoder.joblib'
            self.label_encoder = joblib.load(encoder_path)

            print("✓ Models loaded successfully", file=sys.stderr)

        except Exception as e:
            print(f"Error loading models: {e}", file=sys.stderr)
            sys.exit(1)

    def align_features(self, features_dict):
        """
        Align extracted features with training feature names
        Handle missing features by filling with 0
        """
        expected_features = self.metadata['feature_names']

        # Create a DataFrame with features
        aligned_features = {}

        for feature_name in expected_features:
            if feature_name in features_dict:
                aligned_features[feature_name] = features_dict[feature_name]
            else:
                # Feature not found - fill with 0 or appropriate default
                aligned_features[feature_name] = 0

        # Convert to DataFrame with single row
        df = pd.DataFrame([aligned_features])

        return df

    def predict_single_block(self, features_dict):
        """Predict energy for a single code block"""
        try:
            # Align features to match training data
            features_df = self.align_features(features_dict)

            # Regression prediction (energy in joules)
            energy_transformed = self.regression_model.predict(features_df)[0]

            # Inverse transform (sqrt was applied during training)
            if self.metadata.get('regression_uses_sqrt_transform', False):
                energy_joules = energy_transformed ** 2
            else:
                energy_joules = energy_transformed

            # Classification prediction (Low/Medium/High)
            tier_encoded = self.classification_model.predict(features_df)[0]
            tier_label = self.label_encoder.inverse_transform([tier_encoded])[0]

            # Get probability scores for confidence
            if hasattr(self.classification_model, 'predict_proba'):
                probabilities = self.classification_model.predict_proba(features_df)[0]
                confidence = float(np.max(probabilities))
            else:
                confidence = 1.0

            return {
                'energy_joules': float(energy_joules),
                'energy_tier': tier_label,
                'tier_confidence': confidence,
                'energy_formatted': f"{energy_joules:.6f}J"
            }

        except Exception as e:
            return {
                'error': str(e),
                'energy_joules': None,
                'energy_tier': 'Unknown',
                'tier_confidence': 0.0
            }

    def predict_blocks(self, blocks):
        """Predict energy for multiple code blocks"""
        results = []

        for block in blocks:
            block_features = block.get('features', {})

            prediction = self.predict_single_block(block_features)

            result = {
                'block_type': block.get('block_type'),
                'start_line': block.get('start_line'),
                'end_line': block.get('end_line'),
                **prediction
            }

            results.append(result)

        return results


def main():
    """Main entry point"""
    # Check if we're being called correctly
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        print("Energy predictor loaded successfully", file=sys.stderr)
        sys.exit(0)

    # Initialize predictor
    predictor = EnergyPredictor()

    # Read input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({'error': f'Invalid JSON input: {e}'}))
        sys.exit(1)

    # Check if input is a list of blocks or a single block
    if isinstance(input_data, list):
        blocks = input_data
    elif isinstance(input_data, dict) and 'features' in input_data:
        blocks = [input_data]
    else:
        print(json.dumps({'error': 'Invalid input format. Expected list of blocks or single block with features.'}))
        sys.exit(1)

    # Make predictions
    predictions = predictor.predict_blocks(blocks)

    # Output predictions as JSON
    print(json.dumps(predictions, indent=2))


if __name__ == '__main__':
    main()
