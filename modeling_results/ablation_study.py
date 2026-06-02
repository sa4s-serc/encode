"""
Ablation Study for EnCoDe: Energy Estimation of Source Code At Design-Time
===========================================================================
Addresses reviewer requests for:
  1. Baselines against simple complexity/size proxy metrics
  2. Feature-group ablations showing what each group contributes

Using XGBoost (best model per full evaluation):
  - Regression: log-transformed target, evaluated with R² and RMSE
  - Classification: 3-class (Low/Medium/High), evaluated with Accuracy and macro-F1
"""

import os
import numpy as np
import pandas as pd
from sklearn.model_selection import cross_val_score, StratifiedKFold, KFold
from sklearn.metrics import (r2_score, mean_squared_error,
                              accuracy_score, f1_score)
from sklearn.preprocessing import RobustScaler
from sklearn.pipeline import Pipeline
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Feature group definitions (base 33 features)
# ---------------------------------------------------------------------------
GROUPS = {
    'AST Structural': [
        'feature_total_nodes', 'feature_unique_node_types',
        'feature_max_depth', 'feature_avg_depth', 'feature_depth_variance',
        'feature_avg_branching_factor', 'feature_max_branching_factor',
        'feature_leaves_to_nodes_ratio',
    ],
    'Complexity': [
        'feature_cyclomatic_complexity', 'feature_cognitive_complexity',
        'feature_nesting_complexity', 'feature_control_flow_complexity',
    ],
    'Density': [
        'feature_operator_density', 'feature_literal_density',
        'feature_call_density', 'feature_variable_density',
        'feature_attribute_density',
    ],
    'Entropy': [
        'feature_node_type_entropy', 'feature_operator_entropy',
        'feature_variable_entropy',
    ],
    'Counts': [
        'feature_unique_variables', 'feature_unique_operators',
        'feature_unique_functions', 'feature_loops_count',
        'feature_conditionals_count', 'feature_functions_count',
        'feature_classes_count', 'feature_try_blocks_count',
    ],
    'Halstead': [
        'feature_vocabulary_size', 'feature_program_length',
        'feature_program_volume', 'feature_program_difficulty',
        'feature_program_effort',
    ],
}

ALL_FEATURES = [f for feats in GROUPS.values() for f in feats]  # 33 features

# Baseline feature subsets (proxy metrics reviewers highlighted)
BASELINES = {
    'Size-only':
        ['feature_total_nodes', 'feature_program_length'],
    'Complexity+Size':
        # cyclomatic + cognitive + nesting + Halstead (classic "complexity proxy")
        GROUPS['Complexity'] + GROUPS['Halstead'],
}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data():
    X_train = pd.read_csv(os.path.join(DATA_DIR, 'X_train_base_features.csv'), index_col=0)
    X_test  = pd.read_csv(os.path.join(DATA_DIR, 'X_test_base_features.csv'),  index_col=0)
    targets = pd.read_csv(os.path.join(DATA_DIR, 'target_variables.csv'),       index_col=0)

    y_train_raw = targets.loc[X_train.index, 'energy_train']
    y_test_raw  = targets.loc[X_test.index,  'energy_test']

    # Regression targets: log1p-transformed (matches original script's 'log' transformation)
    y_train_log = np.log1p(y_train_raw)
    y_test_log  = np.log1p(y_test_raw)

    # Classification targets: equal-frequency 3-class bins (same as paper)
    bins     = pd.qcut(y_train_raw, q=3, labels=[0, 1, 2])
    thresholds = [y_train_raw.quantile(1/3), y_train_raw.quantile(2/3)]
    y_train_cls = bins.astype(int)
    # Apply same thresholds to test set
    y_test_cls = pd.cut(
        y_test_raw,
        bins=[-np.inf, thresholds[0], thresholds[1], np.inf],
        labels=[0, 1, 2]
    ).astype(int)

    return X_train, X_test, y_train_log, y_test_log, y_train_cls, y_test_cls


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def make_reg_pipeline(random_state=42):
    # Hyperparameters match the original regression_models.py script
    model = xgb.XGBRegressor(
        n_estimators=200, learning_rate=0.05, max_depth=5,
        subsample=0.72, colsample_bytree=0.72,
        reg_alpha=0.7, reg_lambda=0.7,
        min_child_weight=7, gamma=0.06,
        random_state=random_state, eval_metric='rmse',
        verbosity=0, n_jobs=-1
    )
    return Pipeline([('scaler', RobustScaler()), ('model', model)])


def make_clf_pipeline(random_state=42):
    model = xgb.XGBClassifier(
        n_estimators=200, learning_rate=0.1, max_depth=6,
        random_state=random_state, eval_metric='mlogloss',
        verbosity=0, n_jobs=-1
    )
    return Pipeline([('scaler', RobustScaler()), ('model', model)])


def eval_regression(X_train, y_train, X_test, y_test, features, cv_folds=5):
    Xtr = X_train[features].values
    Xte = X_test[features].values
    pipe = make_reg_pipeline()
    pipe.fit(Xtr, y_train.values)
    pred_test = pipe.predict(Xte)
    test_r2   = r2_score(y_test.values, pred_test)
    test_rmse = np.sqrt(mean_squared_error(y_test.values, pred_test))

    cv_scores = cross_val_score(
        make_reg_pipeline(), Xtr, y_train.values,
        cv=KFold(n_splits=cv_folds, shuffle=True, random_state=42),
        scoring='r2', n_jobs=-1
    )
    return {
        'test_r2':    round(test_r2, 4),
        'test_rmse':  round(test_rmse, 4),
        'cv_r2_mean': round(cv_scores.mean(), 4),
        'cv_r2_std':  round(cv_scores.std(), 4),
    }


def eval_classification(X_train, y_train, X_test, y_test, features, cv_folds=5):
    Xtr = X_train[features].values
    Xte = X_test[features].values
    pipe = make_clf_pipeline()
    pipe.fit(Xtr, y_train.values)
    pred_test = pipe.predict(Xte)
    test_acc  = accuracy_score(y_test.values, pred_test)
    test_f1   = f1_score(y_test.values, pred_test, average='macro')

    cv_scores = cross_val_score(
        make_clf_pipeline(), Xtr, y_train.values,
        cv=StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42),
        scoring='accuracy', n_jobs=-1
    )
    return {
        'test_acc':    round(test_acc, 4),
        'test_f1':     round(test_f1, 4),
        'cv_acc_mean': round(cv_scores.mean(), 4),
        'cv_acc_std':  round(cv_scores.std(), 4),
    }


# ---------------------------------------------------------------------------
# Main ablation loop
# ---------------------------------------------------------------------------

def run_ablation():
    print("Loading data …")
    X_train, X_test, y_train_log, y_test_log, y_train_cls, y_test_cls = load_data()

    configs = {}

    # 1. Simple baselines
    for name, feats in BASELINES.items():
        configs[name] = feats

    # 2. Full model (all 33 base features)
    configs['Full Model (all groups)'] = ALL_FEATURES

    # 3. Leave-one-group-out ablations
    for grp_name, grp_feats in GROUPS.items():
        remaining = [f for f in ALL_FEATURES if f not in grp_feats]
        configs[f'w/o {grp_name}'] = remaining

    # 4. Single-group-only (to see standalone value)
    for grp_name, grp_feats in GROUPS.items():
        configs[f'Only {grp_name}'] = grp_feats

    reg_rows = []
    clf_rows = []

    total = len(configs)
    for i, (label, feats) in enumerate(configs.items(), 1):
        print(f"[{i:2d}/{total}] {label} ({len(feats)} features) …", end=' ', flush=True)
        reg = eval_regression(X_train, y_train_log, X_test, y_test_log, feats)
        clf = eval_classification(X_train, y_train_cls, X_test, y_test_cls, feats)
        print(f"R²={reg['test_r2']:.3f}  Acc={clf['test_acc']:.3f}")

        row_base = {'Configuration': label, 'Features': len(feats)}
        reg_rows.append({**row_base, **reg})
        clf_rows.append({**row_base, **clf})

    df_reg = pd.DataFrame(reg_rows)
    df_clf = pd.DataFrame(clf_rows)

    out_reg = os.path.join(DATA_DIR, 'ablation_regression_results.csv')
    out_clf = os.path.join(DATA_DIR, 'ablation_classification_results.csv')
    df_reg.to_csv(out_reg, index=False)
    df_clf.to_csv(out_clf, index=False)
    print(f"\nSaved --> {out_reg}")
    print(f"Saved --> {out_clf}")

    # Pretty-print summary tables
    print("\n" + "="*70)
    print("REGRESSION ABLATION (XGBoost, log-transform target)")
    print("="*70)
    print(df_reg.to_string(index=False))

    print("\n" + "="*70)
    print("CLASSIFICATION ABLATION (XGBoost, 3-class Low/Med/High)")
    print("="*70)
    print(df_clf.to_string(index=False))

    return df_reg, df_clf


if __name__ == '__main__':
    run_ablation()
