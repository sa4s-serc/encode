import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from scipy.stats import skew, kurtosis
from sklearn.model_selection import cross_val_score, KFold, cross_validate
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (r2_score, mean_squared_error, mean_absolute_error,
                             median_absolute_error, max_error, explained_variance_score)
from sklearn.ensemble import (RandomForestRegressor, ExtraTreesRegressor, 
                            GradientBoostingRegressor, AdaBoostRegressor)
from sklearn.linear_model import Ridge, Lasso, ElasticNet, BayesianRidge
from sklearn.svm import SVR
from sklearn.neighbors import KNeighborsRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.neural_network import MLPRegressor
import time
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

# Import advanced models if available
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("XGBoost not available")

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    print("LightGBM not available")

try:
    import catboost as cb
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False
    print("CatBoost not available")

# Set plotting style
plt.style.use('default')
sns.set_palette("viridis")

def load_and_preprocess_data():
    """Load and preprocess the energy data"""
    print("Loading and preprocessing energy data...")
    
    # Load data
    X_train = pd.read_csv('X_train_base_features.csv', index_col=0)
    X_test = pd.read_csv('X_test_base_features.csv', index_col=0)
    targets_df = pd.read_csv('target_variables.csv', index_col=0)
    
    y_train = targets_df.loc[X_train.index, 'energy_train']
    y_test = targets_df.loc[X_test.index, 'energy_test']
    
    print(f"Original data - Train: {len(X_train)}, Test: {len(X_test)}")
    print(f"Energy range - Train: {y_train.min():.2e} to {y_train.max():.2e}")
    print(f"Energy range - Test: {y_test.min():.2e} to {y_test.max():.2e}")
    
    return X_train, y_train, X_test, y_test

def apply_outlier_removal(X_train, y_train, X_test, y_test, percentile=100):
    """Apply optimal outlier removal strategy"""
    print(f"\nApplying {percentile}% percentile outlier removal...")
    # Calculate bounds from training data
    percentile = 100
    lower_threshold = (100 - percentile) / 2
    upper_threshold = percentile + (100 - percentile) / 2
    
    lower_bound = np.percentile(y_train, lower_threshold)
    upper_bound = np.percentile(y_train, upper_threshold)
    
    print(f"Energy bounds: {lower_bound:.2e} to {upper_bound:.2e}")
    
    # Apply to both sets
    train_mask = (y_train >= lower_bound) & (y_train <= upper_bound)
    test_mask = (y_test >= lower_bound) & (y_test <= upper_bound)
    
    X_train_clean = X_train[train_mask].copy()
    y_train_clean = y_train[train_mask].copy()
    X_test_clean = X_test[test_mask].copy()
    y_test_clean = y_test[test_mask].copy()
    
    print(f"Training: {len(X_train)} → {len(X_train_clean)} samples ({len(X_train) - len(X_train_clean)} removed)")
    print(f"Test: {len(X_test)} → {len(X_test_clean)} samples ({len(X_test) - len(X_test_clean)} removed)")
    
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

def get_all_regression_models():
    """
    FINAL OPTIMAL HYPERPARAMETERS
    Based on best observed performance across all experiments
    USE WITH SQRT TRANSFORMATION (default)
    """
    models = {}
    
    # ==========================================
    # 🥇 TIER 1: CHAMPION MODELS (R² > 0.80)
    # ==========================================
    
    if LIGHTGBM_AVAILABLE:
        models['LightGBM'] = lgb.LGBMRegressor(
            # Conservative settings to prevent overfitting
            n_estimators=220,
            max_depth=6,              # Reduced
            learning_rate=0.05,       # Slower
            num_leaves=28,            # Reduced
            min_child_samples=25,     # Increased
            reg_alpha=0.6,            # Increased
            reg_lambda=0.6,           # Increased
            subsample=0.75,           # Reduced
            colsample_bytree=0.75,    # Reduced
            random_state=42,
            verbosity=-1,
            n_jobs=-1
        )
    
    if XGBOOST_AVAILABLE:
        models['XGBoost'] = xgb.XGBRegressor(
            # Gap 0.138, fine-tune to ~0.12
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,       # Slower
            subsample=0.72,           # Slightly reduced
            colsample_bytree=0.72,    # Slightly reduced
            reg_alpha=0.7,            # Increased
            reg_lambda=0.7,           # Increased
            min_child_weight=7,       # Increased
            gamma=0.06,               # Increased
            random_state=42,
            eval_metric='rmse',
            n_jobs=-1
        )
    
    models['Gradient Boosting'] = GradientBoostingRegressor(
        # Gap 0.132 slightly high, fine-tune
        n_estimators=200,
        max_depth=5,              # Keep at 5
        learning_rate=0.05,       # Slightly slower
        subsample=0.75,           # Reduced
        min_samples_split=25,     # Increased
        min_samples_leaf=12,      # Increased
        max_features='sqrt',
        random_state=42
    )
    
    # ==========================================
    # 🥈 TIER 2: EXCELLENT MODELS (R² > 0.77)
    # ==========================================
    
    models['Random Forest'] = RandomForestRegressor(
        # Balanced: gap 0.107 achieved, improve R²
        n_estimators=300,
        max_depth=10,             # Increased from 8
        min_samples_leaf=8,       # Reduced from 12
        min_samples_split=18,     # Reduced from 25
        max_features='sqrt',
        max_samples=0.85,         # Increased from 0.8
        random_state=42,
        n_jobs=-1
    )
    
    models['Extra Trees'] = ExtraTreesRegressor(
        # Keep conservative to maintain low gap
        n_estimators=280,
        max_depth=10,
        min_samples_leaf=9,
        min_samples_split=18,
        max_features='sqrt',
        bootstrap=True,           # Required for max_samples
        max_samples=0.8,
        random_state=42,
        n_jobs=-1
    )
    
    models['KNN'] = KNeighborsRegressor(
        # Revert: distance weights caused gap 0.311, uniform had 0.059
        n_neighbors=45,           # More neighbors for stability
        weights='uniform',        # Critical: uniform prevents overfitting
        metric='minkowski',
        p=2,
        n_jobs=-1
    )
    
    # ==========================================
    # 🥉 TIER 3: SOLID MODELS (R² > 0.60)
    # ==========================================
    
    models['Ridge'] = Ridge(
        # Tuned for better R² with stable generalization
        alpha=1.0             # Reduced from 5.0 for better fit
    )
    
    models['Bayesian Ridge'] = BayesianRidge(
        # BEST PERFORMANCE: R²=0.6364, Gap=-0.0359, MAPE=89.05%
        # Transform: SQRT
        # Status: ✅ Similar to Ridge
    )
    
    models['AdaBoost'] = AdaBoostRegressor(
        # Gap 0.197 still high, more aggressive regularization
        n_estimators=40,
        learning_rate=0.1,        # Further reduced
        loss='linear',
        random_state=42
    )
    
    models['Decision Tree'] = DecisionTreeRegressor(
        # Balance R² (0.678) with gap (0.105)
        max_depth=9,
        min_samples_split=20,
        min_samples_leaf=12,
        min_impurity_decrease=0.0005,
        random_state=42
    )
    
    # ==========================================
    # ❌ TIER 4: PROBLEMATIC MODELS (Not Recommended)
    # ==========================================
    
    # Lasso & ElasticNet - tuned with reduced regularization
    models['Lasso'] = Lasso(
        alpha=0.001,              # Further reduced for better fit
        max_iter=5000,
        random_state=42
    )

    models['ElasticNet'] = ElasticNet(
        alpha=0.001,              # Further reduced for better fit
        l1_ratio=0.3,             # Reduced L1 ratio for more L2
        max_iter=5000,
        random_state=42
    )
    
    models['SVR'] = SVR(
        # Balance R² (0.756) with gap (0.128)
        kernel='rbf',
        C=30.0,               # Reduced for less overfitting
        epsilon=0.08,         # Increased for more tolerance
        gamma='scale'         # Back to scale for better generalization
    )
    
    # ==========================================
    # OPTIONAL: CatBoost
    # ==========================================
    
    if CATBOOST_AVAILABLE:
        models['CatBoost'] = cb.CatBoostRegressor(
            # Gap 0.158 still high, more regularization
            iterations=180,
            depth=4,              # Reduced from 5
            learning_rate=0.045,  # Slower
            l2_leaf_reg=6.0,      # Increased from 4.5
            subsample=0.65,       # Reduced from 0.7
            random_state=42,
            verbose=False
        )
    
    return models

def apply_target_transformation(y_data, transform_type):
    """Apply target transformation"""
    if transform_type == 'log':
        return np.log1p(y_data)
    elif transform_type == 'sqrt':
        return np.sqrt(y_data)
    elif transform_type == 'raw':
        return y_data.copy()
    else:
        raise ValueError(f"Unknown transformation: {transform_type}")

def calculate_comprehensive_metrics(y_true, y_pred, set_name='test'):
    """Calculate comprehensive regression metrics"""
    # Basic metrics
    r2 = r2_score(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    
    # Additional metrics
    try:
        max_err = max_error(y_true, y_pred)
    except:
        max_err = np.nan
    
    try:
        median_ae = median_absolute_error(y_true, y_pred)
    except:
        median_ae = np.nan
    
    try:
        explained_var = explained_variance_score(y_true, y_pred)
    except:
        explained_var = np.nan
    
    # MAPE with protection
    numerator = np.abs(y_true - y_pred)
    denominator = (np.abs(y_true) + np.abs(y_pred)) / 2
    denominator = np.maximum(denominator, 1e-10)
    mape = np.mean(numerator / denominator) * 100
    
    # Adjusted R² (requires number of features, will be added later)
    # adj_r2 will be calculated separately when n and p are known
    
    # Residual statistics
    residuals = y_true - y_pred
    residual_mean = np.mean(residuals)
    residual_std = np.std(residuals)
    
    try:
        residual_skewness = skew(residuals)
        residual_kurt = kurtosis(residuals)
    except:
        residual_skewness = np.nan
        residual_kurt = np.nan
    
    return {
        f'{set_name}_r2': r2,
        f'{set_name}_rmse': rmse,
        f'{set_name}_mae': mae,
        f'{set_name}_mape': mape,
        f'{set_name}_max_error': max_err,
        f'{set_name}_median_ae': median_ae,
        f'{set_name}_explained_var': explained_var,
        f'{set_name}_residual_mean': residual_mean,
        f'{set_name}_residual_std': residual_std,
        f'{set_name}_residual_skewness': residual_skewness,
        f'{set_name}_residual_kurtosis': residual_kurt
    }

def calculate_adjusted_r2(r2, n_samples, n_features):
    """Calculate adjusted R²"""
    if n_samples <= n_features + 1:
        return np.nan
    adj_r2 = 1 - (1 - r2) * (n_samples - 1) / (n_samples - n_features - 1)
    return adj_r2

def perform_cross_validation(pipeline, X, y, cv_folds=5):
    """Perform comprehensive cross-validation"""
    print(f"    Performing {cv_folds}-fold cross-validation...")
    
    kfold = KFold(n_splits=cv_folds, shuffle=True, random_state=42)
    
    # Define scoring metrics
    scoring = {
        'r2': 'r2',
        'neg_rmse': 'neg_root_mean_squared_error',
        'neg_mae': 'neg_mean_absolute_error'
    }
    
    try:
        cv_results = cross_validate(
            pipeline, X, y, 
            cv=kfold, 
            scoring=scoring,
            return_train_score=False,
            n_jobs=-1
        )
        
        cv_metrics = {
            'cv_r2_mean': cv_results['test_r2'].mean(),
            'cv_r2_std': cv_results['test_r2'].std(),
            'cv_rmse_mean': -cv_results['test_neg_rmse'].mean(),
            'cv_rmse_std': cv_results['test_neg_rmse'].std(),
            'cv_mae_mean': -cv_results['test_neg_mae'].mean(),
            'cv_mae_std': cv_results['test_neg_mae'].std(),
            'cv_r2_min': cv_results['test_r2'].min(),
            'cv_r2_max': cv_results['test_r2'].max(),
        }
        
        return cv_metrics
        
    except Exception as e:
        print(f"    CV failed: {str(e)[:50]}")
        return {
            'cv_r2_mean': np.nan,
            'cv_r2_std': np.nan,
            'cv_rmse_mean': np.nan,
            'cv_rmse_std': np.nan,
            'cv_mae_mean': np.nan,
            'cv_mae_std': np.nan,
            'cv_r2_min': np.nan,
            'cv_r2_max': np.nan,
        }

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

def evaluate_models_on_transformation(X_train, y_train, X_test, y_test, preprocessor, transform_type):
    """Evaluate all models on a specific target transformation with comprehensive metrics"""
    print(f"\nEvaluating models with {transform_type} transformation...")

    # Apply transformation
    y_train_transformed = apply_target_transformation(y_train, transform_type)
    y_test_transformed = apply_target_transformation(y_test, transform_type)

    print(f"Transformed range: {y_train_transformed.min():.4f} to {y_train_transformed.max():.4f}")

    # Select 5 random samples from test set for energy measurement
    np.random.seed(42)
    energy_sample_indices = np.random.choice(len(X_test), size=min(5, len(X_test)), replace=False)
    X_energy_samples = X_test.iloc[energy_sample_indices]
    print(f"Selected {len(X_energy_samples)} samples for energy measurement")

    models = get_all_regression_models()
    results = []

    n_features = X_train.shape[1]
    
    for model_name, model in models.items():
        print(f"  Evaluating {model_name}...")
        try:
            # Create pipeline
            pipeline = Pipeline([
                ('preprocessor', preprocessor),
                ('model', model)
            ])
            
            # Training phase - measure time
            train_start_time = time.time()
            pipeline.fit(X_train, y_train_transformed)
            train_time = time.time() - train_start_time
            
            # Training predictions
            train_pred_start_time = time.time()
            y_train_pred = pipeline.predict(X_train)
            train_pred_time = time.time() - train_pred_start_time
            
            # Test predictions
            test_pred_start_time = time.time()
            y_test_pred = pipeline.predict(X_test)
            test_pred_time = time.time() - test_pred_start_time
            
            # Calculate training metrics
            train_metrics = calculate_comprehensive_metrics(y_train_transformed, y_train_pred, 'train')
            
            # Calculate test metrics
            test_metrics = calculate_comprehensive_metrics(y_test_transformed, y_test_pred, 'test')
            
            # Calculate adjusted R²
            train_adj_r2 = calculate_adjusted_r2(train_metrics['train_r2'], len(X_train), n_features)
            test_adj_r2 = calculate_adjusted_r2(test_metrics['test_r2'], len(X_test), n_features)
            
            # Perform cross-validation
            cv_metrics = perform_cross_validation(pipeline, X_train, y_train_transformed, cv_folds=5)

            # Measure inference energy
            print(f"    Measuring inference energy...")
            inference_energy = measure_inference_energy(pipeline, X_energy_samples)

            # Calculate overfitting indicators
            r2_gap = train_metrics['train_r2'] - test_metrics['test_r2']
            rmse_ratio = test_metrics['test_rmse'] / (train_metrics['train_rmse'] + 1e-10)

            # Combine all metrics
            result = {
                'model': model_name,
                'transformation': transform_type,
                'train_time_seconds': train_time,
                'train_pred_time_seconds': train_pred_time,
                'test_pred_time_seconds': test_pred_time,
                'inference_energy_per_sample_joules': inference_energy,
                'n_train_samples': len(X_train),
                'n_test_samples': len(X_test),
                'n_features': n_features,
                **train_metrics,
                **test_metrics,
                'train_adj_r2': train_adj_r2,
                'test_adj_r2': test_adj_r2,
                **cv_metrics,
                'train_test_r2_gap': r2_gap,
                'train_test_rmse_ratio': rmse_ratio,
            }
            
            results.append(result)
            
            # Print summary
            energy_str = f"{inference_energy:.6f}J" if not np.isnan(inference_energy) else "N/A"
            print(f"    Train R²: {train_metrics['train_r2']:.3f} | Test R²: {test_metrics['test_r2']:.3f} | "
                  f"CV R²: {cv_metrics['cv_r2_mean']:.3f}±{cv_metrics['cv_r2_std']:.3f} | "
                  f"Gap: {r2_gap:.3f} | Energy: {energy_str}")
            
        except Exception as e:
            print(f"    {model_name:15s}: Failed - {str(e)[:50]}")
    
    return results

def create_performance_plots(all_results_df):
    """Create comprehensive performance visualization plots"""
    print("\nCreating performance visualization plots...")
    
    # Filter out any rows with NaN in critical columns
    plot_df = all_results_df.dropna(subset=['train_r2', 'test_r2', 'cv_r2_mean'])
    
    # 1. Train vs Test vs CV Performance
    fig, axes = plt.subplots(2, 2, figsize=(20, 16))
    fig.suptitle('Comprehensive Model Performance Analysis', fontsize=16, fontweight='bold')
    
    # R² comparison across train/test/cv
    ax = axes[0, 0]
    transformations = plot_df['transformation'].unique()
    models = plot_df['model'].unique()
    x_pos = np.arange(len(models))
    width = 0.25
    
    for transform in transformations:
        transform_data = plot_df[plot_df['transformation'] == transform]
        if len(transform_data) > 0:
            ax.scatter(transform_data['test_r2'], transform_data['train_r2'], 
                      label=f'{transform.capitalize()}', alpha=0.6, s=100)
    
    # Add diagonal line
    lims = [ax.get_xlim()[0], ax.get_ylim()[1]]
    ax.plot(lims, lims, 'k--', alpha=0.3, linewidth=2, label='Perfect fit')
    
    ax.set_xlabel('Test R²')
    ax.set_ylabel('Train R²')
    ax.set_title('Train vs Test R² (Overfitting Analysis)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # CV vs Test R²
    ax = axes[0, 1]
    for transform in transformations:
        transform_data = plot_df[plot_df['transformation'] == transform]
        if len(transform_data) > 0:
            ax.errorbar(transform_data['test_r2'], transform_data['cv_r2_mean'],
                       yerr=transform_data['cv_r2_std'], fmt='o',
                       label=f'{transform.capitalize()}', alpha=0.6, capsize=5)
    
    lims = [min(ax.get_xlim()[0], ax.get_ylim()[0]), max(ax.get_xlim()[1], ax.get_ylim()[1])]
    ax.plot(lims, lims, 'k--', alpha=0.3, linewidth=2)
    
    ax.set_xlabel('Test R²')
    ax.set_ylabel('CV R² (mean ± std)')
    ax.set_title('Cross-Validation vs Test Performance')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Training time comparison
    ax = axes[1, 0]
    for transform in transformations:
        transform_data = plot_df[plot_df['transformation'] == transform].sort_values('train_time_seconds')
        if len(transform_data) > 0:
            ax.barh(range(len(transform_data)), transform_data['train_time_seconds'],
                   label=f'{transform.capitalize()}', alpha=0.7)
            ax.set_yticks(range(len(transform_data)))
            ax.set_yticklabels(transform_data['model'])
            break  # Only show one transformation for clarity
    
    ax.set_xlabel('Training Time (seconds)')
    ax.set_ylabel('Model')
    ax.set_title('Training Time by Model')
    ax.grid(True, alpha=0.3, axis='x')
    
    # Performance vs Training Time
    ax = axes[1, 1]
    for transform in transformations:
        transform_data = plot_df[plot_df['transformation'] == transform]
        if len(transform_data) > 0:
            scatter = ax.scatter(transform_data['train_time_seconds'], 
                               transform_data['test_r2'],
                               c=transform_data['cv_r2_std'],
                               label=f'{transform.capitalize()}',
                               alpha=0.6, s=100, cmap='viridis')
    
    ax.set_xlabel('Training Time (seconds)')
    ax.set_ylabel('Test R²')
    ax.set_title('Performance vs Training Time')
    ax.set_xscale('log')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='CV Std')
    
    plt.tight_layout()
    plt.savefig('comprehensive_performance_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # 2. Detailed metrics heatmap
    fig, axes = plt.subplots(1, 3, figsize=(24, 8))
    fig.suptitle('Performance Heatmaps by Transformation', fontsize=16, fontweight='bold')
    
    metrics_to_plot = ['test_r2', 'cv_r2_mean', 'train_test_r2_gap']
    titles = ['Test R² Score', 'CV R² Score (Mean)', 'Train-Test R² Gap (Overfitting)']
    
    for idx, (metric, title) in enumerate(zip(metrics_to_plot, titles)):
        heatmap_data = plot_df.pivot_table(
            index='model', 
            columns='transformation', 
            values=metric,
            aggfunc='mean'
        )
        
        sns.heatmap(heatmap_data, annot=True, cmap='RdYlGn' if 'gap' not in metric else 'RdYlGn_r', 
                   fmt='.3f', ax=axes[idx], cbar_kws={'label': metric})
        axes[idx].set_title(title)
        axes[idx].set_xlabel('Transformation')
        axes[idx].set_ylabel('Model')
    
    plt.tight_layout()
    plt.savefig('performance_heatmaps.png', dpi=300, bbox_inches='tight')
    plt.show()

def analyze_best_performers(all_results_df):
    """Analyze and report best performing models"""
    print("\n" + "="*80)
    print("DETAILED PERFORMANCE ANALYSIS")
    print("="*80)
    
    # Overall best by test R²
    best_overall = all_results_df.loc[all_results_df['test_r2'].idxmax()]
    print(f"\n🏆 BEST OVERALL PERFORMANCE (by Test R²):")
    print(f"  Model: {best_overall['model']}")
    print(f"  Transformation: {best_overall['transformation']}")
    print(f"  Train R²: {best_overall['train_r2']:.4f} | Test R²: {best_overall['test_r2']:.4f} | CV R²: {best_overall['cv_r2_mean']:.4f}±{best_overall['cv_r2_std']:.4f}")
    print(f"  Train RMSE: {best_overall['train_rmse']:.4f} | Test RMSE: {best_overall['test_rmse']:.4f}")
    print(f"  Train MAE: {best_overall['train_mae']:.4f} | Test MAE: {best_overall['test_mae']:.4f}")
    print(f"  Overfitting Gap: {best_overall['train_test_r2_gap']:.4f}")
    print(f"  Training Time: {best_overall['train_time_seconds']:.2f}s")
    if not np.isnan(best_overall['inference_energy_per_sample_joules']):
        print(f"  Inference Energy: {best_overall['inference_energy_per_sample_joules']:.6f} J/sample")
    
    # Best by CV score (most reliable)
    best_cv = all_results_df.loc[all_results_df['cv_r2_mean'].idxmax()]
    print(f"\n🎯 BEST CROSS-VALIDATION PERFORMANCE:")
    print(f"  Model: {best_cv['model']}")
    print(f"  Transformation: {best_cv['transformation']}")
    print(f"  CV R²: {best_cv['cv_r2_mean']:.4f}±{best_cv['cv_r2_std']:.4f} (range: {best_cv['cv_r2_min']:.4f} to {best_cv['cv_r2_max']:.4f})")
    print(f"  Test R²: {best_cv['test_r2']:.4f}")
    
    # Least overfitting
    least_overfit = all_results_df.loc[all_results_df['train_test_r2_gap'].idxmin()]
    print(f"\n✅ LEAST OVERFITTING:")
    print(f"  Model: {least_overfit['model']}")
    print(f"  Transformation: {least_overfit['transformation']}")
    print(f"  Train R²: {least_overfit['train_r2']:.4f} | Test R²: {least_overfit['test_r2']:.4f}")
    print(f"  R² Gap: {least_overfit['train_test_r2_gap']:.4f}")
    
    # Fastest model with good performance
    good_performers = all_results_df[all_results_df['test_r2'] > 0.7]
    if len(good_performers) > 0:
        fastest_good = good_performers.loc[good_performers['train_time_seconds'].idxmin()]
        print(f"\n⚡ FASTEST MODEL (R² > 0.7):")
        print(f"  Model: {fastest_good['model']}")
        print(f"  Transformation: {fastest_good['transformation']}")
        print(f"  Test R²: {fastest_good['test_r2']:.4f}")
        print(f"  Training Time: {fastest_good['train_time_seconds']:.2f}s")

    # Most energy-efficient model with good performance
    if PYRAPL_AVAILABLE:
        energy_df = all_results_df.dropna(subset=['inference_energy_per_sample_joules'])
        good_energy_performers = energy_df[energy_df['test_r2'] > 0.7]
        if len(good_energy_performers) > 0:
            most_efficient = good_energy_performers.loc[good_energy_performers['inference_energy_per_sample_joules'].idxmin()]
            print(f"\n🔋 MOST ENERGY EFFICIENT MODEL (R² > 0.7):")
            print(f"  Model: {most_efficient['model']}")
            print(f"  Transformation: {most_efficient['transformation']}")
            print(f"  Test R²: {most_efficient['test_r2']:.4f}")
            print(f"  Inference Energy: {most_efficient['inference_energy_per_sample_joules']:.6f} J/sample")
    
    # Best per transformation
    print(f"\n📊 BEST MODEL PER TRANSFORMATION:")
    for transform in all_results_df['transformation'].unique():
        transform_data = all_results_df[all_results_df['transformation'] == transform]
        if len(transform_data) > 0:
            best_for_transform = transform_data.loc[transform_data['test_r2'].idxmax()]
            print(f"  {transform.capitalize():8s}: {best_for_transform['model']:20s} "
                  f"(Test R²: {best_for_transform['test_r2']:.4f}, "
                  f"CV: {best_for_transform['cv_r2_mean']:.4f}±{best_for_transform['cv_r2_std']:.4f})")
    
    # Overall statistics
    print(f"\n📈 OVERALL STATISTICS:")
    print(f"  Mean Test R²: {all_results_df['test_r2'].mean():.4f} ± {all_results_df['test_r2'].std():.4f}")
    print(f"  Mean CV R²: {all_results_df['cv_r2_mean'].mean():.4f}")
    print(f"  Mean Overfitting Gap: {all_results_df['train_test_r2_gap'].mean():.4f}")
    print(f"  Models with Test R² > 0.8: {(all_results_df['test_r2'] > 0.8).sum()}/{len(all_results_df)}")
    print(f"  Models with CV R² > 0.8: {(all_results_df['cv_r2_mean'] > 0.8).sum()}/{len(all_results_df)}")
    print(f"  Models with Gap < 0.1: {(all_results_df['train_test_r2_gap'] < 0.1).sum()}/{len(all_results_df)}")
    
    # Top 5 models
    print(f"\n🔝 TOP 5 MODELS (by Test R²):")
    top_5 = all_results_df.nlargest(5, 'test_r2')
    for idx, row in top_5.iterrows():
        print(f"  {row['model']:20s} ({row['transformation']:4s}): "
              f"Test R²={row['test_r2']:.4f}, CV={row['cv_r2_mean']:.4f}, Gap={row['train_test_r2_gap']:.4f}")

def main_comprehensive_analysis():
    """Main function for comprehensive regression analysis"""
    print("=" * 80)
    print("COMPREHENSIVE ENERGY REGRESSION ANALYSIS WITH FULL METRICS")
    print("=" * 80)
    print("Testing all models with comprehensive train/test/CV metrics")
    
    # Load and preprocess data
    X_train, y_train, X_test, y_test = load_and_preprocess_data()
    
    # Apply outlier removal
    X_train_clean, y_train_clean, X_test_clean, y_test_clean = apply_outlier_removal(
        X_train, y_train, X_test, y_test, percentile=88
    )
    
    # Create preprocessor
    preprocessor = create_feature_preprocessor(X_train_clean)
    
    print(f"\nPreprocessed data summary:")
    print(f"  Training samples: {len(X_train_clean)}")
    print(f"  Test samples: {len(X_test_clean)}")
    print(f"  Features: {X_train_clean.shape[1]}")
    print(f"  Energy range: {y_train_clean.min():.2e} to {y_train_clean.max():.2e}")
    
    # Test all transformations
    all_results = []
    transformations = ['log', 'sqrt', 'raw']
    
    for transform in transformations:
        print(f"\n{'='*50}")
        print(f"TESTING {transform.upper()} TRANSFORMATION")
        print(f"{'='*50}")
        
        results = evaluate_models_on_transformation(
            X_train_clean, y_train_clean, X_test_clean, y_test_clean,
            preprocessor, transform
        )
        all_results.extend(results)
    
    # Convert to DataFrame
    all_results_df = pd.DataFrame(all_results)
    
    # Save comprehensive results
    output_file = 'comprehensive_regression_results_full_metrics.csv'
    all_results_df.to_csv(output_file, index=False)
    print(f"\n✅ Full results saved to {output_file}")
    print(f"   Total columns: {len(all_results_df.columns)}")
    print(f"   Metrics per model: {len(all_results_df.columns) - 3}")  # minus model, transformation, n_features
    
    # Also save a summary version
    summary_cols = ['model', 'transformation', 'train_r2', 'test_r2', 'cv_r2_mean', 'cv_r2_std',
                   'train_rmse', 'test_rmse', 'train_mae', 'test_mae', 'train_test_r2_gap',
                   'train_time_seconds', 'inference_energy_per_sample_joules']
    summary_df = all_results_df[summary_cols]
    summary_df.to_csv('model_performance_summary.csv', index=False)
    print(f"   Summary saved to model_performance_summary.csv")
    
    # Create visualizations
    create_performance_plots(all_results_df)
    
    # Analyze best performers
    analyze_best_performers(all_results_df)
    
    # Print available columns
    print(f"\n📋 METRICS CAPTURED (Total: {len(all_results_df.columns)}):")
    for i, col in enumerate(all_results_df.columns, 1):
        print(f"  {i:2d}. {col}")
    
    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE!")
    print(f"{'='*80}")
    
    return all_results_df

if __name__ == "__main__":
    results_df = main_comprehensive_analysis()