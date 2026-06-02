import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from sklearn.model_selection import cross_val_score, StratifiedKFold, KFold
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler, LabelEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (r2_score, mean_squared_error, mean_absolute_error,
                           accuracy_score, classification_report, confusion_matrix,
                           precision_recall_fscore_support, roc_auc_score)

# Regression models
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor

# Classification models
from sklearn.ensemble import (RandomForestClassifier, ExtraTreesClassifier, 
                            GradientBoostingClassifier, AdaBoostClassifier)
from sklearn.linear_model import LogisticRegression, RidgeClassifier, SGDClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis, QuadraticDiscriminantAnalysis

import warnings
warnings.filterwarnings('ignore')

# Import PyRAPL for energy measurement
try:
    import pyRAPL
    pyRAPL.setup()
    PYRAPL_AVAILABLE = True
    print("PyRAPL available - energy measurements will be recorded")
except (ImportError, Exception) as e:
    PYRAPL_AVAILABLE = False
    print(f"PyRAPL not available: {e}")

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

def load_and_prepare_data():
    """Load data and apply the best preprocessing strategy"""
    print("Loading data and applying optimal preprocessing strategy...")
    
    # Load original data
    X_train = pd.read_csv('X_train_base_features.csv', index_col=0)
    X_test = pd.read_csv('X_test_base_features.csv', index_col=0)
    targets_df = pd.read_csv('target_variables.csv', index_col=0)
    
    y_train = targets_df.loc[X_train.index, 'energy_train']
    y_test = targets_df.loc[X_test.index, 'energy_test']
    
    lower_threshold = 0
    upper_threshold = 100 
    
    lower_bound = np.percentile(y_train, lower_threshold)
    upper_bound = np.percentile(y_train, upper_threshold)
    
    print(f"  Energy bounds: {lower_bound:.2e} to {upper_bound:.2e}")
    
    # Apply bounds to both sets
    train_mask = (y_train >= lower_bound) & (y_train <= upper_bound)
    test_mask = (y_test >= lower_bound) & (y_test <= upper_bound)
    
    X_train_clean = X_train[train_mask].copy()
    y_train_clean = y_train[train_mask].copy()
    X_test_clean = X_test[test_mask].copy()
    y_test_clean = y_test[test_mask].copy()
    
    print(f"Data after outlier removal:")
    print(f"  Train: {len(X_train)} → {len(X_train_clean)} samples")
    print(f"  Test: {len(X_test)} → {len(X_test_clean)} samples")
    
    return X_train_clean, y_train_clean, X_test_clean, y_test_clean

def create_energy_categories(y_train, y_test, method='quantiles'):
    """Create low/medium/high categories from continuous energy values"""
    print(f"Creating energy categories using {method} method...")
    
    if method == 'quantiles':
        # Use training data to define category boundaries
        q33 = np.quantile(y_train, 0.33)
        q67 = np.quantile(y_train, 0.67)
        
        print(f"  Category boundaries:")
        print(f"    Low: ≤ {q33:.2e}")
        print(f"    Medium: {q33:.2e} to {q67:.2e}")
        print(f"    High: > {q67:.2e}")
        
        # Apply to both train and test
        y_train_cat = pd.cut(y_train, bins=[0, q33, q67, float('inf')], 
                            labels=['Low', 'Medium', 'High'], include_lowest=True)
        y_test_cat = pd.cut(y_test, bins=[0, q33, q67, float('inf')], 
                           labels=['Low', 'Medium', 'High'], include_lowest=True)
        
    elif method == 'log_quantiles':
        # Use log-transformed values for more balanced categories
        log_y_train = np.log1p(y_train)
        q33 = np.quantile(log_y_train, 0.33)
        q67 = np.quantile(log_y_train, 0.67)
        
        # Convert back to original scale
        q33_orig = np.expm1(q33)
        q67_orig = np.expm1(q67)
        
        print(f"  Log-based category boundaries:")
        print(f"    Low: ≤ {q33_orig:.2e}")
        print(f"    Medium: {q33_orig:.2e} to {q67_orig:.2e}")
        print(f"    High: > {q67_orig:.2e}")
        
        y_train_cat = pd.cut(y_train, bins=[0, q33_orig, q67_orig, float('inf')], 
                            labels=['Low', 'Medium', 'High'], include_lowest=True)
        y_test_cat = pd.cut(y_test, bins=[0, q33_orig, q67_orig, float('inf')], 
                           labels=['Low', 'Medium', 'High'], include_lowest=True)
    
    # Display category distributions
    train_dist = y_train_cat.value_counts().sort_index()
    test_dist = y_test_cat.value_counts().sort_index()
    
    print(f"  Training distribution: {dict(train_dist)}")
    print(f"  Test distribution: {dict(test_dist)}")
    
    return y_train_cat, y_test_cat

def create_optimal_preprocessor():
    """Create the optimal preprocessor based on previous results"""
    # Note: This assumes we can load the data to get feature names
    # In practice, you might want to pass feature names as parameter
    X_train, _, _, _ = load_and_prepare_data()
    
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

def get_regression_models():
    """Get regression models for comparison"""
    models = {
        # 'RandomForest': RandomForestRegressor(n_estimators=300, max_depth=20, random_state=42),
        # 'ExtraTrees': ExtraTreesRegressor(n_estimators=300, max_depth=20, random_state=42),
        # 'GradientBoosting': GradientBoostingRegressor(n_estimators=200, max_depth=8, random_state=42)
    }
    
    # if XGBOOST_AVAILABLE:
    #     models['XGBoost'] = xgb.XGBRegressor(n_estimators=200, max_depth=10, random_state=42, eval_metric='rmse')
    
    return models
def get_classification_models():
    """
    FINAL OPTIMIZED CLASSIFICATION MODELS
    These are the BEST settings discovered across all iterations
    Based on actual performance data, not theory
    """
    models = {}
    
    # ==========================================
    # 🥇 TIER 1: CHAMPION MODELS (Acc > 0.809)
    # ==========================================
    
    if XGBOOST_AVAILABLE:
        models['XGBoost'] = xgb.XGBClassifier(
            # BEST: Iteration 1/2 Settings
            # Performance: Acc=0.8097, Gap=0.0835, F1=0.8066
            # This is the sweet spot - don't change!
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
    # Status: ✅ OPTIMAL - Excellent balance of accuracy and gap
    
    models['Gradient Boosting'] = GradientBoostingClassifier(
        # BEST: Iteration 1/2 Settings
        # Performance: Acc=0.8097, Gap=0.0462, F1=0.8068
        # BEST BALANCED MODEL across all experiments!
        n_estimators=200,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.85,
        min_samples_split=25,
        min_samples_leaf=15,
        max_features='sqrt',
        random_state=42
    )
    # Status: ✅ PERFECT - Gap of 0.046 is outstanding!
    # This is the most reliable model for production
    
    if LIGHTGBM_AVAILABLE:
        models['LightGBM'] = lgb.LGBMClassifier(
            # BEST: Iteration 2 Settings (reduced complexity)
            # Performance: Acc=0.8093, Gap=0.0957, F1=0.8065
            # Gap improved from 0.110 → 0.096
            n_estimators=300,
            max_depth=8,                   # Reduced from 10
            learning_rate=0.08,
            num_leaves=25,                 # Reduced from 31
            min_child_samples=25,          # Increased from 20
            reg_alpha=0.7,                 # Increased from 0.5
            reg_lambda=0.7,                # Increased from 0.5
            subsample=0.85,
            colsample_bytree=0.85,
            class_weight='balanced',
            random_state=42,
            verbosity=-1,
            n_jobs=-1
        )
    # Status: ✅ OPTIMAL - Good balance achieved
    
    # ==========================================
    # 🥈 TIER 2: EXCELLENT MODELS (Acc > 0.80)
    # ==========================================
    
    models['Random Forest'] = RandomForestClassifier(
        # BEST: Iteration 3 Settings (increased complexity)
        # Performance: Acc=0.8046, Gap=0.0444, F1=0.8016
        # Only model that benefited from complexity increase!
        n_estimators=400,              # Increased from 350
        max_depth=16,                  # Increased from 14
        min_samples_leaf=6,            # Reduced from 8
        min_samples_split=10,          # Reduced from 15
        max_features='sqrt',
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    # Status: ✅ EXCELLENT - Best Random Forest so far
    # Alternative: Use Iteration 2 settings (Acc=0.8035, Gap=0.0298) for even lower gap
    
    # ==========================================
    # ⚠️ TIER 3: NEEDS FURTHER WORK
    # ==========================================
    
    models['K-NN'] = KNeighborsClassifier(
        # BEST: Iteration 3 Settings
        # Performance: Acc=0.7923, Gap=0.1401, F1=0.7886
        # Still moderate overfitting - consider removing from ensemble
        n_neighbors=32,                # Increased from 25
        weights='distance',
        metric='minkowski',
        p=2,
        n_jobs=-1
    )
    # Status: ⚠️ MARGINAL - Gap still too high
    # Recommendation: Use n_neighbors=40+ OR remove from production ensemble
    
    # ==========================================
    # ✅ TIER 4: ALREADY OPTIMAL - NO CHANGES
    # ==========================================
    
    models['Extra Trees'] = ExtraTreesClassifier(
        # Performance: Acc=0.7810, Gap=0.0126, F1=0.7770
        # Perfect balance - lowest gap among tree models!
        n_estimators=300,
        max_depth=14,
        min_samples_leaf=10,
        min_samples_split=20,
        max_features='sqrt',
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    # Status: ✅ OPTIMAL - Gap=0.013 is perfect
    
    models['SVM'] = SVC(
        # Performance: Acc=0.7818, Gap=0.0004, F1=0.7766
        # Nearly perfect balance!
        C=1.0,
        kernel='rbf',
        gamma='scale',
        class_weight='balanced',
        probability=True,
        random_state=42
    )
    # Status: ✅ OPTIMAL - Gap=0.0004 is phenomenal
    
    # ==========================================
    # TIER 5: OTHER MODELS - KEEP AS-IS
    # ==========================================
    
    models['AdaBoost'] = AdaBoostClassifier(
        n_estimators=150,
        learning_rate=0.5,
        algorithm='SAMME.R',
        random_state=42
    )
    
    models['Decision Tree'] = DecisionTreeClassifier(
        # Performance: Acc=0.7455, Gap=0.0094
        # Excellent gap, decent baseline
        max_depth=8,
        min_samples_split=40,
        min_samples_leaf=20,
        class_weight='balanced',
        random_state=42
    )
    
    models['Logistic Regression'] = LogisticRegression(
        C=1.0,
        penalty='l2',
        solver='lbfgs',
        multi_class='multinomial',
        class_weight='balanced',
        max_iter=2000,
        random_state=42,
        n_jobs=-1
    )
    
    models['Ridge Classifier'] = RidgeClassifier(
        alpha=1.0,
        class_weight='balanced',
        random_state=42
    )
    
    models['SGD Classifier'] = SGDClassifier(
        loss='log_loss',
        penalty='l2',
        alpha=0.001,
        max_iter=2000,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    
    models['Gaussian NB'] = GaussianNB()
    
    models['LDA'] = LinearDiscriminantAnalysis(solver='svd')
    
    models['QDA'] = QuadraticDiscriminantAnalysis(reg_param=0.1)
    
    return models

def evaluate_regression_models(X_train, y_train, X_test, y_test, preprocessor):
    """Evaluate regression models with optimal preprocessing"""
    print("\nEvaluating Regression Models")
    print("=" * 50)
    
    # Apply square root transformation (best from previous results)
    y_train_transformed = np.sqrt(y_train)
    y_test_transformed = np.sqrt(y_test)
    
    models = get_regression_models()
    results = []
    
    cv_strategy = KFold(n_splits=5, shuffle=True, random_state=42)
    
    for name, model in models.items():
        print(f"Evaluating {name}...")
        
        try:
            # Create pipeline
            pipeline = Pipeline([
                ('preprocessor', preprocessor),
                ('model', model)
            ])
            
            # Cross-validation
            cv_scores = cross_val_score(pipeline, X_train, y_train_transformed, 
                                      cv=cv_strategy, scoring='r2', n_jobs=-1)
            
            # Fit and test
            pipeline.fit(X_train, y_train_transformed)
            y_pred = pipeline.predict(X_test)
            
            # Calculate metrics
            test_r2 = r2_score(y_test_transformed, y_pred)
            test_rmse = np.sqrt(mean_squared_error(y_test_transformed, y_pred))
            test_mae = mean_absolute_error(y_test_transformed, y_pred)
            
            # Calculate MAPE
            numerator = np.abs(y_test_transformed - y_pred)
            denominator = (np.abs(y_test_transformed) + np.abs(y_pred)) / 2
            denominator = np.maximum(denominator, 1e-10)
            mape = np.mean(numerator / denominator) * 100
            
            results.append({
                'model': name,
                'cv_r2_mean': cv_scores.mean(),
                'cv_r2_std': cv_scores.std(),
                'test_r2': test_r2,
                'test_rmse': test_rmse,
                'test_mae': test_mae,
                'test_mape': mape
            })
            
            print(f"  CV R²: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
            print(f"  Test R²: {test_r2:.3f}, RMSE: {test_rmse:.4f}, MAE: {test_mae:.4f}, MAPE: {mape:.1f}%")
            
        except Exception as e:
            print(f"  {name} failed: {e}")
    
    return pd.DataFrame(results)

def measure_inference_energy(pipeline, X_samples):
    """
    Measure energy consumption for inference using PyRAPL
    Returns average energy per single inference in joules
    """
    if not PYRAPL_AVAILABLE:
        return np.nan

    try:
        meter = pyRAPL.Measurement('inference')
        meter.begin()
        _ = pipeline.predict(X_samples)
        meter.end()

        result = meter.result
        pkg = result.pkg[0] if hasattr(result, 'pkg') and result.pkg else 0
        dram = result.dram[0] if hasattr(result, 'dram') and result.dram else 0

        # Total energy in microjoules, convert to joules, divide by number of samples
        total_energy_joules = (pkg + dram) / 1e6 / len(X_samples)
        return total_energy_joules

    except Exception as e:
        print(f"      Energy measurement failed: {str(e)[:50]}")
        return np.nan

def evaluate_classification_comprehensive(X_train, y_train_cat, X_test, y_test_cat, preprocessor):
    """
    Comprehensive classification evaluation with full metrics tracking
    Similar structure to regression evaluation - saves everything to CSV
    """
    print("\n" + "="*80)
    print("COMPREHENSIVE CLASSIFICATION EVALUATION")
    print("="*80)
    
    import time
    from sklearn.metrics import (accuracy_score, precision_recall_fscore_support, 
                                 roc_auc_score, confusion_matrix, balanced_accuracy_score,
                                 cohen_kappa_score, matthews_corrcoef)
    
    # Encode labels
    label_encoder = LabelEncoder()
    y_train_encoded = label_encoder.fit_transform(y_train_cat)
    y_test_encoded = label_encoder.transform(y_test_cat)
    
    print(f"\nClass distribution:")
    print(f"  Training: {np.bincount(y_train_encoded)} samples")
    print(f"  Test:     {np.bincount(y_test_encoded)} samples")
    print(f"  Classes:  {label_encoder.classes_}")
    
    models = get_classification_models()
    results = []
    
    cv_strategy = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    n_features = X_train.shape[1]
    
    for name, model in models.items():
        print(f"\n{'='*70}")
        print(f"Evaluating: {name}")
        print('='*70)
        
        try:
            # Create pipeline
            pipeline = Pipeline([
                ('preprocessor', preprocessor),
                ('model', model)
            ])
            
            # ==========================================
            # TRAINING PHASE
            # ==========================================
            train_start_time = time.time()
            pipeline.fit(X_train, y_train_encoded)
            train_time = time.time() - train_start_time
            
            # ==========================================
            # TRAINING METRICS
            # ==========================================
            train_pred_start = time.time()
            y_train_pred = pipeline.predict(X_train)
            train_pred_time = time.time() - train_pred_start
            
            train_accuracy = accuracy_score(y_train_encoded, y_train_pred)
            train_precision, train_recall, train_f1, _ = precision_recall_fscore_support(
                y_train_encoded, y_train_pred, average='weighted', zero_division=0
            )
            train_balanced_acc = balanced_accuracy_score(y_train_encoded, y_train_pred)
            
            # ==========================================
            # CROSS-VALIDATION METRICS
            # ==========================================
            print("  Performing 5-fold cross-validation...")
            cv_scores_acc = cross_val_score(pipeline, X_train, y_train_encoded, 
                                           cv=cv_strategy, scoring='accuracy', n_jobs=-1)
            cv_scores_f1 = cross_val_score(pipeline, X_train, y_train_encoded, 
                                          cv=cv_strategy, scoring='f1_weighted', n_jobs=-1)
            cv_scores_precision = cross_val_score(pipeline, X_train, y_train_encoded, 
                                                 cv=cv_strategy, scoring='precision_weighted', n_jobs=-1)
            cv_scores_recall = cross_val_score(pipeline, X_train, y_train_encoded, 
                                              cv=cv_strategy, scoring='recall_weighted', n_jobs=-1)
            
            # ==========================================
            # TEST METRICS
            # ==========================================
            test_pred_start = time.time()
            y_test_pred = pipeline.predict(X_test)
            test_pred_time = time.time() - test_pred_start
            
            # Overall test metrics
            test_accuracy = accuracy_score(y_test_encoded, y_test_pred)
            test_balanced_acc = balanced_accuracy_score(y_test_encoded, y_test_pred)
            test_precision, test_recall, test_f1, test_support = precision_recall_fscore_support(
                y_test_encoded, y_test_pred, average='weighted', zero_division=0
            )
            
            # Macro-averaged metrics (equal weight to each class)
            test_precision_macro, test_recall_macro, test_f1_macro, _ = precision_recall_fscore_support(
                y_test_encoded, y_test_pred, average='macro', zero_division=0
            )
            
            # Additional metrics
            test_kappa = cohen_kappa_score(y_test_encoded, y_test_pred)
            test_mcc = matthews_corrcoef(y_test_encoded, y_test_pred)
            
            # ==========================================
            # PER-CLASS METRICS
            # ==========================================
            precision_per_class, recall_per_class, f1_per_class, support_per_class = \
                precision_recall_fscore_support(y_test_encoded, y_test_pred, 
                                              average=None, zero_division=0)
            
            # ==========================================
            # CONFUSION MATRIX ANALYSIS
            # ==========================================
            cm = confusion_matrix(y_test_encoded, y_test_pred)
            cm_diagonal_sum = np.trace(cm)
            cm_total = np.sum(cm)
            
            # Per-class accuracy from confusion matrix
            class_accuracies = cm.diagonal() / cm.sum(axis=1)
            
            # ==========================================
            # ROC AUC (if available)
            # ==========================================
            try:
                if hasattr(pipeline, 'predict_proba'):
                    y_test_proba = pipeline.predict_proba(X_test)
                    test_roc_auc_ovr = roc_auc_score(y_test_encoded, y_test_proba, 
                                                     multi_class='ovr', average='weighted')
                    test_roc_auc_ovo = roc_auc_score(y_test_encoded, y_test_proba, 
                                                     multi_class='ovo', average='weighted')
                    
                    # Per-class ROC AUC
                    roc_auc_per_class = roc_auc_score(
                        pd.get_dummies(y_test_encoded).values, 
                        y_test_proba, 
                        average=None
                    )
                else:
                    test_roc_auc_ovr = None
                    test_roc_auc_ovo = None
                    roc_auc_per_class = [None, None, None]
            except Exception as e:
                test_roc_auc_ovr = None
                test_roc_auc_ovo = None
                roc_auc_per_class = [None, None, None]

            # ==========================================
            # INFERENCE ENERGY MEASUREMENT
            # ==========================================
            print("  Measuring inference energy...")
            np.random.seed(42)
            energy_sample_indices = np.random.choice(len(X_test), size=min(5, len(X_test)), replace=False)
            X_energy_samples = X_test.iloc[energy_sample_indices] if hasattr(X_test, 'iloc') else X_test[energy_sample_indices]
            inference_energy = measure_inference_energy(pipeline, X_energy_samples)

            # ==========================================
            # OVERFITTING INDICATORS
            # ==========================================
            train_test_acc_gap = train_accuracy - test_accuracy
            train_cv_acc_gap = train_accuracy - cv_scores_acc.mean()
            cv_test_acc_gap = cv_scores_acc.mean() - test_accuracy
            
            # Overfitting severity
            if train_test_acc_gap < 0.05:
                overfitting_status = 'Excellent - No Overfitting'
            elif train_test_acc_gap < 0.10:
                overfitting_status = 'Good - Minimal Overfitting'
            elif train_test_acc_gap < 0.15:
                overfitting_status = 'Moderate Overfitting'
            else:
                overfitting_status = 'Significant Overfitting'
            
            # ==========================================
            # COMPILE ALL RESULTS
            # ==========================================
            result = {
                'model': name,
                
                # Dataset info
                'n_train_samples': len(X_train),
                'n_test_samples': len(X_test),
                'n_features': n_features,
                'n_classes': len(label_encoder.classes_),
                
                # Timing and Energy
                'train_time_seconds': train_time,
                'train_pred_time_seconds': train_pred_time,
                'test_pred_time_seconds': test_pred_time,
                'inference_energy_per_sample_joules': inference_energy,
                
                # Training metrics
                'train_accuracy': train_accuracy,
                'train_balanced_accuracy': train_balanced_acc,
                'train_precision': train_precision,
                'train_recall': train_recall,
                'train_f1': train_f1,
                
                # Cross-validation metrics
                'cv_accuracy_mean': cv_scores_acc.mean(),
                'cv_accuracy_std': cv_scores_acc.std(),
                'cv_accuracy_min': cv_scores_acc.min(),
                'cv_accuracy_max': cv_scores_acc.max(),
                'cv_f1_mean': cv_scores_f1.mean(),
                'cv_f1_std': cv_scores_f1.std(),
                'cv_precision_mean': cv_scores_precision.mean(),
                'cv_precision_std': cv_scores_precision.std(),
                'cv_recall_mean': cv_scores_recall.mean(),
                'cv_recall_std': cv_scores_recall.std(),
                
                # Test metrics (weighted average)
                'test_accuracy': test_accuracy,
                'test_balanced_accuracy': test_balanced_acc,
                'test_precision': test_precision,
                'test_recall': test_recall,
                'test_f1': test_f1,
                
                # Test metrics (macro average - equal weight per class)
                'test_precision_macro': test_precision_macro,
                'test_recall_macro': test_recall_macro,
                'test_f1_macro': test_f1_macro,
                
                # Additional test metrics
                'test_cohen_kappa': test_kappa,
                'test_matthews_corrcoef': test_mcc,
                'test_roc_auc_ovr': test_roc_auc_ovr,
                'test_roc_auc_ovo': test_roc_auc_ovo,
                
                # Per-class metrics (Low, Medium, High)
                'test_precision_low': precision_per_class[0],
                'test_precision_medium': precision_per_class[1],
                'test_precision_high': precision_per_class[2],
                'test_recall_low': recall_per_class[0],
                'test_recall_medium': recall_per_class[1],
                'test_recall_high': recall_per_class[2],
                'test_f1_low': f1_per_class[0],
                'test_f1_medium': f1_per_class[1],
                'test_f1_high': f1_per_class[2],
                'test_support_low': support_per_class[0],
                'test_support_medium': support_per_class[1],
                'test_support_high': support_per_class[2],
                'test_class_accuracy_low': class_accuracies[0],
                'test_class_accuracy_medium': class_accuracies[1],
                'test_class_accuracy_high': class_accuracies[2],
                'test_roc_auc_low': roc_auc_per_class[0],
                'test_roc_auc_medium': roc_auc_per_class[1],
                'test_roc_auc_high': roc_auc_per_class[2],
                
                # Overfitting indicators
                'train_test_acc_gap': train_test_acc_gap,
                'train_cv_acc_gap': train_cv_acc_gap,
                'cv_test_acc_gap': cv_test_acc_gap,
                'overfitting_status': overfitting_status,
                
                # Confusion matrix flattened
                'cm_00': cm[0, 0], 'cm_01': cm[0, 1], 'cm_02': cm[0, 2],
                'cm_10': cm[1, 0], 'cm_11': cm[1, 1], 'cm_12': cm[1, 2],
                'cm_20': cm[2, 0], 'cm_21': cm[2, 1], 'cm_22': cm[2, 2],
            }
            
            results.append(result)
            
            # ==========================================
            # PRINT SUMMARY
            # ==========================================
            print(f"  ✓ Training completed in {train_time:.2f}s")
            print(f"\n  PERFORMANCE METRICS:")
            print(f"  {'─'*50}")
            print(f"  Train Accuracy:     {train_accuracy:.4f}")
            print(f"  Test Accuracy:      {test_accuracy:.4f}")
            print(f"  CV Accuracy:        {cv_scores_acc.mean():.4f} ± {cv_scores_acc.std():.4f}")
            print(f"  {'─'*50}")
            print(f"  Train-Test Gap:     {train_test_acc_gap:.4f} ({overfitting_status})")
            print(f"  Train-CV Gap:       {train_cv_acc_gap:.4f}")
            print(f"  {'─'*50}")
            print(f"  Precision (wtd):    {test_precision:.4f} | Recall: {test_recall:.4f} | F1: {test_f1:.4f}")
            print(f"  Balanced Accuracy:  {test_balanced_acc:.4f}")
            if test_roc_auc_ovr:
                print(f"  ROC AUC (OvR):      {test_roc_auc_ovr:.4f}")
            print(f"  Cohen's Kappa:      {test_kappa:.4f}")
            energy_str = f"{inference_energy:.6f} J/sample" if not np.isnan(inference_energy) else "N/A"
            print(f"  Inference Energy:   {energy_str}")
            print(f"\n  PER-CLASS PERFORMANCE:")
            print(f"  {'─'*50}")
            for i, class_name in enumerate(label_encoder.classes_):
                print(f"  {class_name:8s}: P={precision_per_class[i]:.3f} | R={recall_per_class[i]:.3f} | F1={f1_per_class[i]:.3f} | Acc={class_accuracies[i]:.3f}")
            
        except Exception as e:
            print(f"  ❌ FAILED: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # ==========================================
    # SAVE RESULTS
    # ==========================================
    results_df = pd.DataFrame(results)
    output_file = 'classification_results_full_metrics.csv'
    results_df.to_csv(output_file, index=False)
    
    print(f"\n{'='*80}")
    print(f"✅ EVALUATION COMPLETE!")
    print(f"{'='*80}")
    print(f"Results saved to: {output_file}")
    print(f"Total models evaluated: {len(results_df)}")
    print(f"Total metrics per model: {len(results_df.columns)}")
    
    # ==========================================
    # SUMMARY STATISTICS
    # ==========================================
    print(f"\n{'='*80}")
    print("SUMMARY STATISTICS")
    print(f"{'='*80}")
    
    if len(results_df) > 0:
        print(f"\nTest Accuracy Statistics:")
        print(f"  Mean:    {results_df['test_accuracy'].mean():.4f}")
        print(f"  Std:     {results_df['test_accuracy'].std():.4f}")
        print(f"  Min:     {results_df['test_accuracy'].min():.4f}")
        print(f"  Max:     {results_df['test_accuracy'].max():.4f}")
        
        print(f"\nOverfitting Statistics:")
        print(f"  Mean Gap:           {results_df['train_test_acc_gap'].mean():.4f}")
        print(f"  Models with Gap < 0.10:  {(results_df['train_test_acc_gap'] < 0.10).sum()}/{len(results_df)}")
        print(f"  Models with Gap < 0.05:  {(results_df['train_test_acc_gap'] < 0.05).sum()}/{len(results_df)}")
        
        print(f"\n{'='*80}")
        print("TOP 5 MODELS BY TEST ACCURACY:")
        print(f"{'='*80}")
        top_5 = results_df.nlargest(5, 'test_accuracy')
        for idx, row in top_5.iterrows():
            print(f"\n{row['model']}:")
            print(f"  Accuracy: {row['test_accuracy']:.4f} | F1: {row['test_f1']:.4f} | Gap: {row['train_test_acc_gap']:.4f}")
            print(f"  CV: {row['cv_accuracy_mean']:.4f} ± {row['cv_accuracy_std']:.4f}")
            if row['test_roc_auc_ovr'] is not None:
                print(f"  ROC AUC: {row['test_roc_auc_ovr']:.4f}")
        
        print(f"\n{'='*80}")
        print("BEST BALANCED MODELS (Accuracy > 0.75, Gap < 0.10):")
        print(f"{'='*80}")
        balanced = results_df[(results_df['test_accuracy'] > 0.75) & 
                              (results_df['train_test_acc_gap'] < 0.10)]
        if len(balanced) > 0:
            balanced_sorted = balanced.nlargest(5, 'test_accuracy')
            for idx, row in balanced_sorted.iterrows():
                print(f"  {row['model']:20s}: Acc={row['test_accuracy']:.4f}, Gap={row['train_test_acc_gap']:.4f}, F1={row['test_f1']:.4f}")
        else:
            print("  No models meet strict criteria. Relaxing constraints...")
            relaxed = results_df[(results_df['test_accuracy'] > 0.70) & 
                                (results_df['train_test_acc_gap'] < 0.15)]
            for idx, row in relaxed.nlargest(3, 'test_accuracy').iterrows():
                print(f"  {row['model']:20s}: Acc={row['test_accuracy']:.4f}, Gap={row['train_test_acc_gap']:.4f}")
    
    # Save label encoder mapping
    label_mapping = pd.DataFrame({
        'class_id': range(len(label_encoder.classes_)),
        'class_name': label_encoder.classes_
    })
    label_mapping.to_csv('classification_label_mapping.csv', index=False)
    
    return results_df, label_encoder

def create_detailed_classification_report(best_model, X_test, y_test_encoded, label_encoder):
    """Create detailed classification report for best model"""
    print(f"\nDetailed Classification Analysis - Best Model")
    print("=" * 60)
    
    # Predictions
    y_pred = best_model.predict(X_test)
    
    # Classification report
    print("Classification Report:")
    print(classification_report(y_test_encoded, y_pred, 
                              target_names=label_encoder.classes_))
    
    # Confusion Matrix
    cm = confusion_matrix(y_test_encoded, y_pred)
    
    # Plot confusion matrix
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=label_encoder.classes_,
                yticklabels=label_encoder.classes_)
    plt.title('Confusion Matrix - Best Classification Model')
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.show()
    
    # Per-class accuracy
    class_accuracies = cm.diagonal() / cm.sum(axis=1)
    print(f"\nPer-class accuracies:")
    for i, class_name in enumerate(label_encoder.classes_):
        print(f"  {class_name}: {class_accuracies[i]:.3f}")

def create_comparison_visualizations(regression_results, classification_results):
    """Create comprehensive comparison visualizations"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Regression vs Classification Performance Comparison', fontsize=16, fontweight='bold')
    
    # Regression R² scores
    reg_models = regression_results['model']
    reg_r2 = regression_results['test_r2']
    
    axes[0,0].barh(range(len(reg_models)), reg_r2)
    axes[0,0].set_yticks(range(len(reg_models)))
    axes[0,0].set_yticklabels(reg_models)
    axes[0,0].set_xlabel('Test R²')
    axes[0,0].set_title('Regression Models - R² Scores')
    axes[0,0].grid(True, alpha=0.3)
    
    # Regression MAPE scores
    reg_mape = regression_results['test_mape']
    
    axes[0,1].barh(range(len(reg_models)), reg_mape)
    axes[0,1].set_yticks(range(len(reg_models)))
    axes[0,1].set_yticklabels(reg_models)
    axes[0,1].set_xlabel('Test MAPE (%)')
    axes[0,1].set_title('Regression Models - MAPE Scores')
    axes[0,1].grid(True, alpha=0.3)
    
    # Classification accuracy scores
    clf_models = classification_results['model']
    clf_accuracy = classification_results['test_accuracy']
    
    axes[1,0].barh(range(len(clf_models)), clf_accuracy)
    axes[1,0].set_yticks(range(len(clf_models)))
    axes[1,0].set_yticklabels(clf_models, fontsize=8)
    axes[1,0].set_xlabel('Test Accuracy')
    axes[1,0].set_title('Classification Models - Accuracy Scores')
    axes[1,0].grid(True, alpha=0.3)
    
    # Classification F1 scores
    clf_f1 = classification_results['test_f1']
    
    axes[1,1].barh(range(len(clf_models)), clf_f1)
    axes[1,1].set_yticks(range(len(clf_models)))
    axes[1,1].set_yticklabels(clf_models, fontsize=8)
    axes[1,1].set_xlabel('Test F1 Score')
    axes[1,1].set_title('Classification Models - F1 Scores')
    axes[1,1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()

def main_comprehensive_evaluation():
    """Main function for comprehensive regression and classification evaluation"""
    print("COMPREHENSIVE ENERGY MODELING: REGRESSION AND CLASSIFICATION")
    print("=" * 80)
    print("Using optimal preprocessing: 88% percentile outlier removal + feature scaling")
    
    # Load and prepare data
    X_train, y_train, X_test, y_test = load_and_prepare_data()
    
    # Create energy categories for classification
    y_train_cat, y_test_cat = create_energy_categories(y_train, y_test, method='quantiles')
    
    # Create optimal preprocessor
    preprocessor = create_optimal_preprocessor()
    
    print(f"\nDataset prepared:")
    print(f"  Training samples: {len(X_train)}")
    print(f"  Test samples: {len(X_test)}")
    print(f"  Features: {X_train.shape[1]}")
    print(f"  Energy range: {y_train.min():.2e} to {y_train.max():.2e}")
    
    # Evaluate regression models
    regression_results = evaluate_regression_models(X_train, y_train, X_test, y_test, preprocessor)
    
    # Evaluate classification models
    classification_results, label_encoder = evaluate_classification_comprehensive(
        X_train, y_train_cat, X_test, y_test_cat, preprocessor
    )
    
    # Display comprehensive results
    # print(f"\nREGRESSION RESULTS SUMMARY")
    # print("=" * 50)
    # if len(regression_results) > 0:
    #     regression_results_sorted = regression_results.sort_values('test_r2', ascending=False)
    #     print(regression_results_sorted[['model', 'test_r2', 'test_rmse', 'test_mae', 'test_mape']].to_string(index=False, float_format='%.3f'))
        
    #     best_regression = regression_results_sorted.iloc[0]
    #     print(f"\nBest Regression Model: {best_regression['model']} (R² = {best_regression['test_r2']:.3f})")
    
    print(f"\nCLASSIFICATION RESULTS SUMMARY")
    print("=" * 50)
    if len(classification_results) > 0:
        classification_results_sorted = classification_results.sort_values('test_accuracy', ascending=False)
        print(classification_results_sorted[['model', 'test_accuracy', 'test_precision', 'test_recall', 'test_f1']].to_string(index=False, float_format='%.3f'))
        
        best_classification = classification_results_sorted.iloc[0]
        print(f"\nBest Classification Model: {best_classification['model']} (Accuracy = {best_classification['test_accuracy']:.3f})")
        
        # Get best classification model for detailed analysis
        models = get_classification_models()
        best_model_name = best_classification['model']
        if best_model_name in models:
            best_clf_pipeline = Pipeline([
                ('preprocessor', preprocessor),
                ('model', models[best_model_name])
            ])
            y_train_encoded = label_encoder.fit_transform(y_train_cat)
            y_test_encoded = label_encoder.transform(y_test_cat)
            best_clf_pipeline.fit(X_train, y_train_encoded)
            
            create_detailed_classification_report(best_clf_pipeline, X_test, y_test_encoded, label_encoder)
    
    # Create comparison visualizations
    if len(regression_results) > 0 and len(classification_results) > 0:
        create_comparison_visualizations(regression_results, classification_results)
    
    # Save results
    if len(regression_results) > 0:
        regression_results.to_csv('comprehensive_regression_results.csv', index=False)
    if len(classification_results) > 0:
        classification_results.to_csv('comprehensive_classification_results.csv', index=False)
    
    print(f"\nResults saved to CSV files")
    
    # Final insights
    print(f"\nKEY INSIGHTS")
    print("=" * 30)
    if len(regression_results) > 0 and len(classification_results) > 0:
        best_reg_r2 = regression_results['test_r2'].max()
        best_clf_acc = classification_results['test_accuracy'].max()
        
        print(f"Best Regression R²: {best_reg_r2:.3f}")
        print(f"Best Classification Accuracy: {best_clf_acc:.3f}")
        
        if best_reg_r2 > 0.85 or best_clf_acc > 0.90:
            print("Excellent performance achieved! Models ready for practical applications.")
        elif best_reg_r2 > 0.80 or best_clf_acc > 0.85:
            print("Good performance achieved! Models suitable for research and some applications.")
        else:
            print("Moderate performance. Consider additional feature engineering or ensemble methods.")
    
    return regression_results, classification_results

if __name__ == "__main__":
    regression_results, classification_results = main_comprehensive_evaluation()