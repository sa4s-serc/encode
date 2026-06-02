# import pandas as pd
# import numpy as np
# import matplotlib.pyplot as plt
# import seaborn as sns
# from scipy import stats
# from scipy.stats import pearsonr, spearmanr, kendalltau
# from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler
# from sklearn.compose import ColumnTransformer
# from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
# from sklearn.tree import DecisionTreeRegressor
# from sklearn.feature_selection import f_regression
# import warnings
# warnings.filterwarnings('ignore')

# # Set plot parameters
# plt.rcParams.update({
#     'font.size': 12,
#     'axes.titlesize': 16,
#     'axes.labelsize': 14,
#     'figure.dpi': 300,
#     'savefig.dpi': 300,
#     'savefig.bbox': 'tight',
# })

# def load_and_prepare_data():
#     """Load data with preprocessing"""
#     print("Loading data...")
    
#     X_train = pd.read_csv('X_train_base_features.csv', index_col=0)
#     X_test = pd.read_csv('X_test_base_features.csv', index_col=0)
#     targets_df = pd.read_csv('target_variables.csv', index_col=0)
    
#     y_train = targets_df.loc[X_train.index, 'energy_train']
#     y_test = targets_df.loc[X_test.index, 'energy_test']
    
#     # Apply outlier removal (88% percentile)
#     lower_bound = np.percentile(y_train, 6)
#     upper_bound = np.percentile(y_train, 94)
    
#     train_mask = (y_train >= lower_bound) & (y_train <= upper_bound)
#     test_mask = (y_test >= lower_bound) & (y_test <= upper_bound)
    
#     X_train_clean = X_train[train_mask].copy()
#     y_train_clean = y_train[train_mask].copy()
#     X_test_clean = X_test[test_mask].copy()
#     y_test_clean = y_test[test_mask].copy()
    
#     # Apply square root transformation
#     y_train_transformed = np.sqrt(y_train_clean)
#     y_test_transformed = np.sqrt(y_test_clean)
    
#     print(f"Data loaded - Train: {len(X_train_clean)}, Test: {len(X_test_clean)}")
    
#     return X_train_clean, y_train_transformed, X_test_clean, y_test_transformed

# def create_feature_groups(feature_names):
#     """Create feature groups"""
#     feature_to_group = {}
    
#     for feature in feature_names:
#         if feature.startswith('block_'):
#             group = 'Block_features'
#         elif '_squared' in feature:
#             group = 'Squared_features'
#         elif '_sqrt' in feature or feature.startswith('sqrt_'):
#             group = 'Square_root_features'
#         elif feature.startswith('log1p_'):
#             group = 'Logarithmic_features'
#         elif feature.startswith('inv_'):
#             group = 'Inverse_features'
#         elif '_x_' in feature:
#             group = 'Interaction_features'
#         elif '_div_' in feature:
#             group = 'Division_features'
#         else:
#             group = 'Original_metrics'
        
#         feature_to_group[feature] = group
    
#     return feature_to_group

# def create_preprocessor(X_train):
#     """Create preprocessor"""
#     feature_groups = {
#         'standard_features': [],      
#         'robust_features': [],        
#         'minmax_features': [],        
#         'binary_features': []         
#     }
    
#     for feature in X_train.columns:
#         if feature.startswith('inv_'):
#             feature_groups['minmax_features'].append(feature)
#         elif any(pattern in feature for pattern in ['_squared', '_x_', '_div_']):
#             feature_groups['robust_features'].append(feature)
#         elif feature.startswith('block_') and '_x_' not in feature:
#             feature_groups['binary_features'].append(feature)
#         else:
#             feature_groups['standard_features'].append(feature)
    
#     transformers = []
#     if feature_groups['standard_features']:
#         transformers.append(('standard', StandardScaler(), feature_groups['standard_features']))
#     if feature_groups['robust_features']:
#         transformers.append(('robust', RobustScaler(), feature_groups['robust_features']))
#     if feature_groups['minmax_features']:
#         transformers.append(('minmax', MinMaxScaler(), feature_groups['minmax_features']))
#     if feature_groups['binary_features']:
#         transformers.append(('binary', 'passthrough', feature_groups['binary_features']))
    
#     return ColumnTransformer(transformers=transformers, remainder='drop')

# def compute_correlations_and_importance(X_train, y_train, X_test, y_test, preprocessor, feature_to_group):
#     """Compute all correlations and importance metrics"""
#     print("\nComputing correlations and importance...")
    
#     # Correlations
#     correlations_data = []
#     for feature in X_train.columns:
#         corr_pearson, p_pearson = pearsonr(X_train[feature], y_train)
#         corr_spearman, p_spearman = spearmanr(X_train[feature], y_train)
        
#         correlations_data.append({
#             'feature': feature,
#             'feature_group': feature_to_group.get(feature, 'Unknown'),
#             'pearson_corr': float(corr_pearson),
#             'abs_pearson': float(abs(corr_pearson)),
#             'pearson_p': float(p_pearson),
#             'spearman_corr': float(corr_spearman),
#             'abs_spearman': float(abs(corr_spearman)),
#         })
    
#     correlations_df = pd.DataFrame(correlations_data)
    
#     # Feature Importance
#     X_train_scaled = preprocessor.fit_transform(X_train)
#     X_test_scaled = preprocessor.transform(X_test)
    
#     # ExtraTrees
#     print("Computing ExtraTrees importance...")
#     et_model = ExtraTreesRegressor(n_estimators=200, max_depth=20, random_state=42, n_jobs=2)
#     et_model.fit(X_train_scaled, y_train)
#     et_importance = et_model.feature_importances_
    
#     # RandomForest
#     print("Computing RandomForest importance...")
#     rf_model = RandomForestRegressor(n_estimators=200, max_depth=20, random_state=42, n_jobs=2)
#     rf_model.fit(X_train_scaled, y_train)
#     rf_importance = rf_model.feature_importances_
    
#     # Average importance
#     avg_importance = (et_importance + rf_importance) / 2
    
#     importance_df = pd.DataFrame({
#         'feature': X_train.columns,
#         'et_importance': et_importance,
#         'rf_importance': rf_importance,
#         'avg_importance': avg_importance
#     })
    
#     # Merge
#     complete_df = correlations_df.merge(importance_df, on='feature')
    
#     return complete_df

# def categorize_features(complete_df, corr_threshold=0.3, imp_percentile=80):
#     """
#     Categorize features into 4 groups based on correlation and importance
    
#     Parameters:
#     - corr_threshold: Threshold for "high" correlation (default 0.3)
#     - imp_percentile: Percentile for "high" importance (default 80 = top 20%)
#     """
#     print("\nCategorizing features...")
#     print(f"Correlation threshold: |r| > {corr_threshold}")
#     print(f"Importance threshold: Top {100-imp_percentile}% (percentile {imp_percentile})")
    
#     # Calculate thresholds
#     importance_threshold = np.percentile(complete_df['avg_importance'], imp_percentile)
    
#     print(f"Importance value threshold: > {importance_threshold:.6f}")
    
#     # Categorize
#     complete_df['high_corr'] = complete_df['abs_pearson'] > corr_threshold
#     complete_df['high_importance'] = complete_df['avg_importance'] > importance_threshold
    
#     # Create category labels
#     def assign_category(row):
#         if row['high_corr'] and row['high_importance']:
#             return 'High_Corr_High_Imp'
#         elif not row['high_corr'] and row['high_importance']:
#             return 'Low_Corr_High_Imp'
#         elif row['high_corr'] and not row['high_importance']:
#             return 'High_Corr_Low_Imp'
#         else:
#             return 'Low_Corr_Low_Imp'
    
#     complete_df['category'] = complete_df.apply(assign_category, axis=1)
    
#     # Print summary
#     print("\n" + "="*70)
#     print("FEATURE CATEGORIZATION SUMMARY")
#     print("="*70)
    
#     for category in ['High_Corr_High_Imp', 'Low_Corr_High_Imp', 'High_Corr_Low_Imp', 'Low_Corr_Low_Imp']:
#         count = (complete_df['category'] == category).sum()
#         pct = count / len(complete_df) * 100
#         print(f"{category.replace('_', ' ')}: {count} features ({pct:.1f}%)")
    
#     return complete_df, importance_threshold

# def save_categorized_features(complete_df):
#     """Save features by category to separate files"""
#     print("\nSaving categorized features to files...")
    
#     categories = {
#         'High_Corr_High_Imp': 'Strong Linear Predictors',
#         'Low_Corr_High_Imp': 'Non-Linear Patterns',
#         'High_Corr_Low_Imp': 'Redundant Features',
#         'Low_Corr_Low_Imp': 'Weak Predictors'
#     }
    
#     for cat_key, cat_name in categories.items():
#         cat_df = complete_df[complete_df['category'] == cat_key].copy()
#         cat_df = cat_df.sort_values('avg_importance', ascending=False)
        
#         # Select relevant columns
#         output_df = cat_df[[
#             'feature', 'feature_group', 
#             'pearson_corr', 'abs_pearson', 'pearson_p',
#             'spearman_corr', 'abs_spearman',
#             'et_importance', 'rf_importance', 'avg_importance'
#         ]].copy()
        
#         # Rename columns
#         output_df.columns = [
#             'Feature_Name', 'Feature_Category',
#             'Pearson_r', 'Abs_Pearson', 'Pearson_p',
#             'Spearman_rho', 'Abs_Spearman',
#             'ExtraTrees_Imp', 'RandomForest_Imp', 'Avg_Importance'
#         ]
        
#         # Save
#         filename = f"features_{cat_key.lower()}"
#         output_df.to_csv(f"{filename}.csv", index=False)
#         output_df.to_excel(f"{filename}.xlsx", index=False, engine='openpyxl')
        
#         print(f"✓ Saved: {filename}.csv/.xlsx ({len(cat_df)} features)")
        
#         # Print top 5 for this category
#         print(f"  Top 5 {cat_name}:")
#         for i, row in output_df.head(5).iterrows():
#             print(f"    {i+1}. {row['Feature_Name']}")

# def create_2x2_matrix_table(complete_df):
#     """Create 2x2 matrix table data"""
#     print("\nGenerating 2×2 Matrix Table...")
    
#     categories = {
#         'High_Corr_High_Imp': 'Strong Linear Predictors',
#         'Low_Corr_High_Imp': 'Non-Linear Patterns',
#         'High_Corr_Low_Imp': 'Redundant Features',
#         'Low_Corr_Low_Imp': 'Weak Predictors'
#     }
    
#     matrix_data = []
    
#     for cat_key, cat_name in categories.items():
#         cat_df = complete_df[complete_df['category'] == cat_key].copy()
#         cat_df = cat_df.sort_values('avg_importance', ascending=False)
        
#         # Statistics
#         count = len(cat_df)
#         pct = count / len(complete_df) * 100
#         mean_corr = cat_df['abs_pearson'].mean()
#         mean_imp = cat_df['avg_importance'].mean()
        
#         # Top 3 features
#         top_features = cat_df.head(3)['feature'].tolist()
#         top_features_str = ', '.join(top_features)
        
#         matrix_data.append({
#             'Category': cat_name,
#             'Count': count,
#             'Percentage': f"{pct:.1f}%",
#             'Mean_Abs_Correlation': f"{mean_corr:.4f}",
#             'Mean_Importance': f"{mean_imp:.6f}",
#             'Top_3_Examples': top_features_str
#         })
    
#     matrix_df = pd.DataFrame(matrix_data)
    
#     # Save
#     matrix_df.to_csv('feature_2x2_matrix_table.csv', index=False)
#     matrix_df.to_excel('feature_2x2_matrix_table.xlsx', index=False, engine='openpyxl')
    
#     print("✓ Saved: feature_2x2_matrix_table.csv/.xlsx")
    
#     # Print formatted table
#     print("\n" + "="*100)
#     print("2×2 MATRIX TABLE - LATEX READY DATA")
#     print("="*100)
#     print("\nHIGH IMPORTANCE (Top 20%)")
#     print("-" * 100)
    
#     # High Corr + High Imp
#     hc_hi = complete_df[complete_df['category'] == 'High_Corr_High_Imp']
#     print(f"\nHIGH CORRELATION (|r| > 0.3) + HIGH IMPORTANCE")
#     print(f"  Count: {len(hc_hi)} ({len(hc_hi)/len(complete_df)*100:.1f}%)")
#     print(f"  Interpretation: Strong linear predictors")
#     print(f"  Mean |r|: {hc_hi['abs_pearson'].mean():.4f}")
#     print(f"  Mean Importance: {hc_hi['avg_importance'].mean():.6f}")
#     print(f"  Top 5 examples:")
#     for i, feat in enumerate(hc_hi.nlargest(5, 'avg_importance')['feature'], 1):
#         print(f"    {i}. {feat}")
    
#     # Low Corr + High Imp
#     lc_hi = complete_df[complete_df['category'] == 'Low_Corr_High_Imp']
#     print(f"\nLOW CORRELATION (|r| ≤ 0.3) + HIGH IMPORTANCE")
#     print(f"  Count: {len(lc_hi)} ({len(lc_hi)/len(complete_df)*100:.1f}%)")
#     print(f"  Interpretation: Non-linear patterns (KEY FINDING!)")
#     print(f"  Mean |r|: {lc_hi['abs_pearson'].mean():.4f}")
#     print(f"  Mean Importance: {lc_hi['avg_importance'].mean():.6f}")
#     print(f"  Top 5 examples:")
#     for i, feat in enumerate(lc_hi.nlargest(5, 'avg_importance')['feature'], 1):
#         print(f"    {i}. {feat}")
    
#     print("\nLOW IMPORTANCE (Bottom 80%)")
#     print("-" * 100)
    
#     # High Corr + Low Imp
#     hc_li = complete_df[complete_df['category'] == 'High_Corr_Low_Imp']
#     print(f"\nHIGH CORRELATION (|r| > 0.3) + LOW IMPORTANCE")
#     print(f"  Count: {len(hc_li)} ({len(hc_li)/len(complete_df)*100:.1f}%)")
#     print(f"  Interpretation: Redundant features (correlated with better predictors)")
#     print(f"  Mean |r|: {hc_li['abs_pearson'].mean():.4f}")
#     print(f"  Mean Importance: {hc_li['avg_importance'].mean():.6f}")
    
#     # Low Corr + Low Imp
#     lc_li = complete_df[complete_df['category'] == 'Low_Corr_Low_Imp']
#     print(f"\nLOW CORRELATION (|r| ≤ 0.3) + LOW IMPORTANCE")
#     print(f"  Count: {len(lc_li)} ({len(lc_li)/len(complete_df)*100:.1f}%)")
#     print(f"  Interpretation: Weak predictors (consider removing)")
#     print(f"  Mean |r|: {lc_li['abs_pearson'].mean():.4f}")
#     print(f"  Mean Importance: {lc_li['avg_importance'].mean():.6f}")
    
#     print("\n" + "="*100)
    
#     return matrix_df

# def create_scatter_plot_all_features(X_train, y_train, complete_df):
#     """Create scatter plot with ALL features colored by category"""
#     print("\nCreating scatter plot for ALL features...")
    
#     # Define colors for each category
#     category_colors = {
#         'High_Corr_High_Imp': '#2E86C1',   # Blue - Strong linear
#         'Low_Corr_High_Imp': '#E74C3C',    # Red - Non-linear (important!)
#         'High_Corr_Low_Imp': '#F39C12',    # Orange - Redundant
#         'Low_Corr_Low_Imp': '#95A5A6'      # Gray - Weak
#     }
    
#     category_labels = {
#         'High_Corr_High_Imp': 'High Corr + High Imp (Strong Linear)',
#         'Low_Corr_High_Imp': 'Low Corr + High Imp (Non-Linear)',
#         'High_Corr_Low_Imp': 'High Corr + Low Imp (Redundant)',
#         'Low_Corr_Low_Imp': 'Low Corr + Low Imp (Weak)'
#     }
    
#     # Create figure
#     fig, ax = plt.subplots(figsize=(14, 10))
    
#     # Plot each category
#     for category in ['Low_Corr_Low_Imp', 'High_Corr_Low_Imp', 'High_Corr_High_Imp', 'Low_Corr_High_Imp']:
#         cat_features = complete_df[complete_df['category'] == category]['feature'].tolist()
        
#         for feature in cat_features:
#             ax.scatter(complete_df[complete_df['feature'] == feature]['abs_pearson'],
#                       complete_df[complete_df['feature'] == feature]['avg_importance'],
#                       color=category_colors[category],
#                       alpha=0.6,
#                       s=50,
#                       edgecolors='white',
#                       linewidth=0.5,
#                       label=category_labels[category] if feature == cat_features[0] else "")
    
#     # Add threshold lines
#     corr_threshold = 0.3
#     imp_threshold = np.percentile(complete_df['avg_importance'], 80)
    
#     ax.axvline(corr_threshold, color='black', linestyle='--', linewidth=2, alpha=0.5, label='Correlation Threshold')
#     ax.axhline(imp_threshold, color='black', linestyle='--', linewidth=2, alpha=0.5, label='Importance Threshold')
    
#     # Labels and title
#     ax.set_xlabel('Absolute Pearson Correlation |r|', fontweight='bold', fontsize=14)
#     ax.set_ylabel('Average Feature Importance (ExtraTrees + RandomForest)', fontweight='bold', fontsize=14)
#     ax.set_title('Feature Categorization: Correlation vs. Importance\n(All Features Colored by Category)', 
#                  fontweight='bold', fontsize=16, pad=20)
    
#     # Legend
#     handles, labels = ax.get_legend_handles_labels()
#     by_label = dict(zip(labels, handles))
#     ax.legend(by_label.values(), by_label.keys(), loc='upper left', framealpha=0.95, fontsize=11)
    
#     ax.grid(True, alpha=0.3, linestyle='--')
    
#     # Add annotations for quadrants
#     ax.text(0.7, imp_threshold * 1.5, 'Strong Linear\nPredictors', 
#            fontsize=12, fontweight='bold', color=category_colors['High_Corr_High_Imp'],
#            ha='center', va='center',
#            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor=category_colors['High_Corr_High_Imp'], linewidth=2))
    
#     ax.text(0.15, imp_threshold * 1.5, 'Non-Linear\nPatterns', 
#            fontsize=12, fontweight='bold', color=category_colors['Low_Corr_High_Imp'],
#            ha='center', va='center',
#            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor=category_colors['Low_Corr_High_Imp'], linewidth=2))
    
#     ax.text(0.7, imp_threshold * 0.5, 'Redundant\nFeatures', 
#            fontsize=12, fontweight='bold', color=category_colors['High_Corr_Low_Imp'],
#            ha='center', va='center',
#            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor=category_colors['High_Corr_Low_Imp'], linewidth=2))
    
#     ax.text(0.15, imp_threshold * 0.5, 'Weak\nPredictors', 
#            fontsize=12, fontweight='bold', color=category_colors['Low_Corr_Low_Imp'],
#            ha='center', va='center',
#            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor=category_colors['Low_Corr_Low_Imp'], linewidth=2))
    
#     plt.tight_layout()
#     plt.savefig('all_features_correlation_vs_importance_scatter.png', dpi=300, bbox_inches='tight')
#     plt.close()
    
#     print("✓ Saved: all_features_correlation_vs_importance_scatter.png")
    
#     # Print statistics
#     print("\nPlot Statistics:")
#     for category, color in category_colors.items():
#         count = (complete_df['category'] == category).sum()
#         print(f"  {category_labels[category]}: {count} features ({color})")

# def create_category_distribution_plots(complete_df):
#     """Create additional distribution plots by category"""
#     print("\nCreating category distribution plots...")
    
#     category_colors = {
#         'High_Corr_High_Imp': '#2E86C1',
#         'Low_Corr_High_Imp': '#E74C3C',
#         'High_Corr_Low_Imp': '#F39C12',
#         'Low_Corr_Low_Imp': '#95A5A6'
#     }
    
#     category_labels = {
#         'High_Corr_High_Imp': 'Strong Linear',
#         'Low_Corr_High_Imp': 'Non-Linear',
#         'High_Corr_Low_Imp': 'Redundant',
#         'Low_Corr_Low_Imp': 'Weak'
#     }
    
#     # 1. Feature group distribution by category
#     fig, axes = plt.subplots(2, 2, figsize=(16, 12))
#     axes = axes.flatten()
    
#     for i, (category, color) in enumerate(category_colors.items()):
#         cat_df = complete_df[complete_df['category'] == category]
#         group_counts = cat_df['feature_group'].value_counts()
        
#         axes[i].barh(range(len(group_counts)), group_counts.values, color=color, alpha=0.7, edgecolor='white', linewidth=2)
#         axes[i].set_yticks(range(len(group_counts)))
#         axes[i].set_yticklabels([g.replace('_', ' ') for g in group_counts.index], fontsize=10)
#         axes[i].set_xlabel('Count', fontweight='bold')
#         axes[i].set_title(f'{category_labels[category]}\n({len(cat_df)} features)', 
#                          fontweight='bold', fontsize=14)
#         axes[i].grid(True, alpha=0.3, axis='x')
        
#         # Add counts on bars
#         for j, (val, idx) in enumerate(zip(group_counts.values, range(len(group_counts)))):
#             axes[i].text(val + 0.5, idx, str(val), va='center', fontweight='bold')
    
#     plt.tight_layout()
#     plt.savefig('category_feature_group_distribution.png', dpi=300, bbox_inches='tight')
#     plt.close()
    
#     print("✓ Saved: category_feature_group_distribution.png")
    
#     # 2. Box plots comparing categories
#     fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    
#     # Correlation distribution
#     data_corr = [complete_df[complete_df['category'] == cat]['abs_pearson'].values 
#                  for cat in category_colors.keys()]
#     bp1 = axes[0].boxplot(data_corr, 
#                           labels=[category_labels[cat] for cat in category_colors.keys()],
#                           patch_artist=True,
#                           showmeans=True)
    
#     for patch, color in zip(bp1['boxes'], category_colors.values()):
#         patch.set_facecolor(color)
#         patch.set_alpha(0.7)
    
#     axes[0].set_ylabel('Absolute Pearson Correlation', fontweight='bold', fontsize=12)
#     axes[0].set_title('Correlation Distribution by Category', fontweight='bold', fontsize=14)
#     axes[0].grid(True, alpha=0.3, axis='y')
#     plt.setp(axes[0].xaxis.get_majorticklabels(), rotation=45, ha='right')
    
#     # Importance distribution
#     data_imp = [complete_df[complete_df['category'] == cat]['avg_importance'].values 
#                 for cat in category_colors.keys()]
#     bp2 = axes[1].boxplot(data_imp,
#                           labels=[category_labels[cat] for cat in category_colors.keys()],
#                           patch_artist=True,
#                           showmeans=True)
    
#     for patch, color in zip(bp2['boxes'], category_colors.values()):
#         patch.set_facecolor(color)
#         patch.set_alpha(0.7)
    
#     axes[1].set_ylabel('Average Feature Importance', fontweight='bold', fontsize=12)
#     axes[1].set_title('Importance Distribution by Category', fontweight='bold', fontsize=14)
#     axes[1].grid(True, alpha=0.3, axis='y')
#     plt.setp(axes[1].xaxis.get_majorticklabels(), rotation=45, ha='right')
    
#     plt.tight_layout()
#     plt.savefig('category_distributions_boxplot.png', dpi=300, bbox_inches='tight')
#     plt.close()
    
#     print("✓ Saved: category_distributions_boxplot.png")

# def main():
#     """Main execution"""
#     print("="*80)
#     print("FEATURE CATEGORIZATION ANALYSIS")
#     print("Correlation vs. Importance")
#     print("="*80)
    
#     # Load data
#     X_train, y_train, X_test, y_test = load_and_prepare_data()
    
#     # Create feature groups
#     feature_to_group = create_feature_groups(X_train.columns)
    
#     # Create preprocessor
#     preprocessor = create_preprocessor(X_train)
    
#     # Compute correlations and importance
#     complete_df = compute_correlations_and_importance(X_train, y_train, X_test, y_test, 
#                                                      preprocessor, feature_to_group)
    
#     # Categorize features
#     complete_df, imp_threshold = categorize_features(complete_df, 
#                                                      corr_threshold=0.3, 
#                                                      imp_percentile=80)
    
#     # Save categorized features to separate files
#     save_categorized_features(complete_df)
    
#     # Create 2x2 matrix table
#     matrix_df = create_2x2_matrix_table(complete_df)
    
#     # Create scatter plot with all features
#     create_scatter_plot_all_features(X_train, y_train, complete_df)
    
#     # Create additional distribution plots
#     create_category_distribution_plots(complete_df)
    
#     # Save complete dataset with categories
#     complete_output = complete_df[[
#         'feature', 'feature_group', 'category',
#         'pearson_corr', 'abs_pearson', 'pearson_p',
#         'spearman_corr', 'abs_spearman',
#         'et_importance', 'rf_importance', 'avg_importance'
#     ]].copy()
    
#     complete_output.columns = [
#         'Feature_Name', 'Feature_Category', 'Analysis_Category',
#         'Pearson_r', 'Abs_Pearson', 'Pearson_p',
#         'Spearman_rho', 'Abs_Spearman',
#         'ExtraTrees_Imp', 'RandomForest_Imp', 'Avg_Importance'
#     ]
    
#     complete_output = complete_output.sort_values('Avg_Importance', ascending=False)
#     complete_output.to_csv('complete_features_with_categories.csv', index=False)
#     complete_output.to_excel('complete_features_with_categories.xlsx', index=False, engine='openpyxl')
#     print("\n✓ Saved: complete_features_with_categories.csv/.xlsx")
    
#     print("\n" + "="*80)
#     print("FILES GENERATED:")
#     print("="*80)
#     print("\n=== CATEGORIZED FEATURE FILES (4 files) ===")
#     print("✓ features_high_corr_high_imp.csv/.xlsx")
#     print("✓ features_low_corr_high_imp.csv/.xlsx")
#     print("✓ features_high_corr_low_imp.csv/.xlsx")
#     print("✓ features_low_corr_low_imp.csv/.xlsx")
#     print("\n=== SUMMARY FILES ===")
#     print("✓ complete_features_with_categories.csv/.xlsx")
#     print("✓ feature_2x2_matrix_table.csv/.xlsx")
#     print("\n=== VISUALIZATIONS ===")
#     print("✓ all_features_correlation_vs_importance_scatter.png")
#     print("✓ category_feature_group_distribution.png")
#     print("✓ category_distributions_boxplot.png")
#     print("="*80)
    
#     return complete_df

# if __name__ == "__main__":
#     results = main()

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from scipy.stats import pearsonr, spearmanr, kendalltau
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor, ExtraTreesRegressor
from sklearn.inspection import permutation_importance
import warnings
warnings.filterwarnings('ignore')

# Import XGBoost
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("⚠️ XGBoost not available")

# Set plot parameters
plt.rcParams.update({
    'font.size': 12,
    'axes.titlesize': 16,
    'axes.labelsize': 14,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
})

def load_and_prepare_data(transformation='raw', remove_outliers=False, outlier_percentile=6):
    """
    Load data with optional preprocessing

    Parameters:
    -----------
    transformation : str, default='raw'
        Type of transformation to apply to target variable
        Options: 'raw', 'sqrt', 'log', 'log1p'
    remove_outliers : bool, default=False
        Whether to remove outliers from the data
    outlier_percentile : float, default=6
        If remove_outliers=True, removes bottom and top percentiles
        (e.g., 6 removes 6% from bottom and 6% from top)
    """
    print("Loading data...")
    print(f"  Transformation: {transformation}")
    print(f"  Remove outliers: {remove_outliers}")
    if remove_outliers:
        print(f"  Outlier percentile: {outlier_percentile}% (keeping {100-2*outlier_percentile}% of data)")

    X_train = pd.read_csv('X_train_base_features.csv', index_col=0)
    X_test = pd.read_csv('X_test_base_features.csv', index_col=0)
    targets_df = pd.read_csv('target_variables.csv', index_col=0)

    y_train = targets_df.loc[X_train.index, 'energy_train']
    y_test = targets_df.loc[X_test.index, 'energy_test']

    # Optional outlier removal
    if remove_outliers:
        lower_bound = np.percentile(y_train, outlier_percentile)
        upper_bound = np.percentile(y_train, 100 - outlier_percentile)

        train_mask = (y_train >= lower_bound) & (y_train <= upper_bound)
        test_mask = (y_test >= lower_bound) & (y_test <= upper_bound)

        X_train = X_train[train_mask].copy()
        y_train = y_train[train_mask].copy()
        X_test = X_test[test_mask].copy()
        y_test = y_test[test_mask].copy()

        print(f"  Outliers removed - Train: {len(X_train)}, Test: {len(X_test)}")
    else:
        print(f"  No outlier removal - Train: {len(X_train)}, Test: {len(X_test)}")

    # Apply transformation
    if transformation == 'raw':
        y_train_transformed = y_train.copy()
        y_test_transformed = y_test.copy()
        print("  Using raw values (no transformation)")
    elif transformation == 'sqrt':
        y_train_transformed = np.sqrt(y_train)
        y_test_transformed = np.sqrt(y_test)
        print("  Applied square root transformation")
    elif transformation == 'log':
        y_train_transformed = np.log(y_train)
        y_test_transformed = np.log(y_test)
        print("  Applied natural log transformation")
    elif transformation == 'log1p':
        y_train_transformed = np.log1p(y_train)
        y_test_transformed = np.log1p(y_test)
        print("  Applied log1p transformation")
    else:
        raise ValueError(f"Unknown transformation: {transformation}")

    print(f"Data loaded - Train: {len(X_train)}, Test: {len(X_test)}")

    return X_train, y_train_transformed, X_test, y_test_transformed

def create_feature_groups(feature_names):
    """Create feature groups"""
    feature_to_group = {}
    
    for feature in feature_names:
        if feature.startswith('block_'):
            group = 'Block_features'
        elif '_squared' in feature:
            group = 'Squared_features'
        elif '_sqrt' in feature or feature.startswith('sqrt_'):
            group = 'Square_root_features'
        elif feature.startswith('log1p_'):
            group = 'Logarithmic_features'
        elif feature.startswith('inv_'):
            group = 'Inverse_features'
        elif '_x_' in feature:
            group = 'Interaction_features'
        elif '_div_' in feature:
            group = 'Division_features'
        else:
            group = 'Original_metrics'
    
        feature_to_group[feature] = group
    
    return feature_to_group

def create_preprocessor(X_train):
    """Create preprocessor"""
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

def compute_feature_importance_for_paper(X_train, y_train, X_test, y_test, preprocessor, feature_to_group):
    """
    Compute ONLY the most reliable and interpretable metrics for publication:
    1. Correlations (Pearson, Spearman, Kendall)
    2. Permutation Importance from 2 best models (Gradient Boosting, XGBoost)
    3. Random Forest importance as baseline (optional)
    """
    print("\n" + "="*80)
    print("COMPUTING FEATURE IMPORTANCE FOR PUBLICATION")
    print("="*80 + "\n")
    
    feature_names = X_train.columns.tolist()
    results = {'feature': feature_names}
    
    # ==========================================
    # 1. CORRELATIONS (Statistical Relationships)
    # ==========================================
    print("1. Computing Correlations...")
    
    pearson_corr, pearson_p = [], []
    spearman_corr, spearman_p = [], []
    kendall_corr, kendall_p = [], []
    
    for feature in feature_names:
        # Pearson (linear)
        r_p, p_p = pearsonr(X_train[feature], y_train)
        pearson_corr.append(float(r_p))
        pearson_p.append(float(p_p))
        
        # Spearman (monotonic)
        r_s, p_s = spearmanr(X_train[feature], y_train)
        spearman_corr.append(float(r_s))
        spearman_p.append(float(p_s))
        
        # Kendall (ordinal)
        r_k, p_k = kendalltau(X_train[feature], y_train)
        kendall_corr.append(float(r_k))
        kendall_p.append(float(p_k))
    
    results['pearson_corr'] = pearson_corr
    results['abs_pearson'] = [abs(r) for r in pearson_corr]
    results['pearson_pval'] = pearson_p
    results['spearman_corr'] = spearman_corr
    results['abs_spearman'] = [abs(r) for r in spearman_corr]
    results['kendall_corr'] = kendall_corr
    results['abs_kendall'] = [abs(r) for r in kendall_corr]
    
    print("   ✓ Correlations computed")
    
    # ==========================================
    # 2. TRANSFORM DATA
    # ==========================================
    print("\n2. Transforming data...")
    X_train_scaled = preprocessor.fit_transform(X_train)
    X_test_scaled = preprocessor.transform(X_test)
    print("   ✓ Data transformed")
    
    # ==========================================
    # 3. PERMUTATION IMPORTANCE (MOST RELIABLE)
    # ==========================================
    print("\n3. Computing Permutation Importance (Gold Standard)...")
    
    # Model 1: Gradient Boosting
    print("   - Gradient Boosting...")
    gb_model = GradientBoostingRegressor(
        n_estimators=300,
        max_depth=7,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_split=15,
        min_samples_leaf=6,
        max_features='sqrt',
        random_state=42
    )
    gb_model.fit(X_train_scaled, y_train)
    
    gb_perm = permutation_importance(
        gb_model, X_test_scaled, y_test,
        n_repeats=10, random_state=42, n_jobs=-1
    )
    results['gradboost_perm_importance'] = gb_perm.importances_mean
    results['gradboost_perm_std'] = gb_perm.importances_std
    print("     ✓ Gradient Boosting permutation importance computed")
    
    # Model 2: XGBoost
    if XGBOOST_AVAILABLE:
        print("   - XGBoost...")
        xgb_model = xgb.XGBRegressor(
            n_estimators=350,
            max_depth=8,
            learning_rate=0.07,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_alpha=0.05,
            reg_lambda=0.15,
            min_child_weight=3,
            random_state=42,
            eval_metric='rmse',
            n_jobs=-1
        )
        xgb_model.fit(X_train_scaled, y_train)
        
        xgb_perm = permutation_importance(
            xgb_model, X_test_scaled, y_test,
            n_repeats=10, random_state=42, n_jobs=-1
        )
        results['xgboost_perm_importance'] = xgb_perm.importances_mean
        results['xgboost_perm_std'] = xgb_perm.importances_std
        print("     ✓ XGBoost permutation importance computed")
    
    # ==========================================
    # 4. RANDOM FOREST BASELINE (Optional)
    # ==========================================
    print("\n4. Computing Random Forest Importance (Baseline)...")
    rf_model = RandomForestRegressor(
        n_estimators=350,
        max_depth=15,
        min_samples_leaf=5,
        min_samples_split=10,
        max_features='sqrt',
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train_scaled, y_train)
    results['randomforest_importance'] = rf_model.feature_importances_
    print("   ✓ Random Forest importance computed")

    # ==========================================
    # 5. EXTRA TREES IMPORTANCE
    # ==========================================
    print("\n5. Computing Extra Trees Importance...")
    et_model = ExtraTreesRegressor(
        n_estimators=350,
        max_depth=15,
        min_samples_leaf=5,
        min_samples_split=10,
        max_features='sqrt',
        random_state=42,
        n_jobs=-1
    )
    et_model.fit(X_train_scaled, y_train)
    results['extratrees_importance'] = et_model.feature_importances_
    print("   ✓ Extra Trees importance computed")

    # ==========================================
    # 6. CREATE DATAFRAME & AGGREGATES
    # ==========================================
    print("\n6. Creating results DataFrame...")
    
    complete_df = pd.DataFrame(results)
    complete_df['feature_group'] = complete_df['feature'].map(feature_to_group)
    
    # Average permutation importance (MAIN METRIC)
    perm_cols = [col for col in complete_df.columns if 'perm_importance' in col]
    if perm_cols:
        complete_df['avg_perm_importance'] = complete_df[perm_cols].mean(axis=1)
    
    # Average absolute correlation
    complete_df['avg_abs_corr'] = (complete_df['abs_pearson'] + 
                                    complete_df['abs_spearman'] + 
                                    complete_df['abs_kendall']) / 3
    
    print("   ✓ Complete DataFrame created")
    
    print("\n" + "="*80)
    print("FEATURE IMPORTANCE COMPUTATION COMPLETE")
    print("="*80)
    
    return complete_df

def create_publication_ranking_table(complete_df, top_n=20):
    """
    Create clean publication-ready ranking table
    Focus on most important metrics only
    """
    print("\n" + "="*80)
    print(f"CREATING TOP {top_n} RANKING TABLE FOR PUBLICATION")
    print("="*80 + "\n")
    
    # Define the key methods to include
    ranking_methods = {
        'Pearson_r': ('abs_pearson', 'Pearson Correlation'),
        'Spearman_rho': ('abs_spearman', 'Spearman Correlation'),
        'GradBoost_Perm': ('gradboost_perm_importance', 'Gradient Boosting'),
        'Avg_Perm_Imp': ('avg_perm_importance', 'Average Permutation')
    }
    
    # Add XGBoost if available
    if 'xgboost_perm_importance' in complete_df.columns:
        ranking_methods['XGBoost_Perm'] = ('xgboost_perm_importance', 'XGBoost')

    # Add RF baseline (optional)
    ranking_methods['RF_Imp'] = ('randomforest_importance', 'Random Forest')

    # Add Extra Trees baseline
    ranking_methods['ET_Imp'] = ('extratrees_importance', 'Extra Trees')
    
    # Create ranking data
    ranking_data = []
    
    for rank in range(1, top_n + 1):
        row = {'Rank': rank}
        
        for method_short, (column_name, method_full) in ranking_methods.items():
            if column_name in complete_df.columns:
                top_features = complete_df.nlargest(top_n, column_name)
                
                if rank <= len(top_features):
                    feature = top_features.iloc[rank-1]['feature']
                    value = top_features.iloc[rank-1][column_name]
                    row[method_short] = feature
                    row[f'{method_short}_val'] = value
                else:
                    row[method_short] = ''
                    row[f'{method_short}_val'] = np.nan
        
        ranking_data.append(row)
    
    ranking_df = pd.DataFrame(ranking_data)
    
    # Save full version with values
    ranking_df.to_csv(f'top{top_n}_features_ranking_with_values.csv', index=False)
    print(f"✓ Saved: top{top_n}_features_ranking_with_values.csv")
    
    # Create publication version (features only)
    pub_columns = ['Rank'] + [k for k in ranking_methods.keys()]
    pub_df = ranking_df[pub_columns]
    
    pub_df.to_csv(f'top{top_n}_features_ranking_publication.csv', index=False)
    pub_df.to_excel(f'top{top_n}_features_ranking_publication.xlsx', index=False, engine='openpyxl')
    print(f"✓ Saved: top{top_n}_features_ranking_publication.csv/.xlsx")
    
    # Create simplified LaTeX table
    create_latex_table_clean(pub_df, ranking_methods, top_n)
    
    # Print top 10 for each method
    print("\n" + "="*70)
    print("TOP 10 FEATURES BY EACH METHOD")
    print("="*70)
    
    for method_short, (column_name, method_full) in ranking_methods.items():
        if column_name in complete_df.columns:
            print(f"\n{method_full}:")
            top10 = complete_df.nlargest(10, column_name)[['feature', column_name]]
            for i, (_, row) in enumerate(top10.iterrows(), 1):
                print(f"  {i:2d}. {row['feature']:45s} {row[column_name]:.6f}")
    
    return ranking_df, pub_df

def create_latex_table_clean(pub_df, methods, top_n):
    """Create clean LaTeX table for publication"""
    print(f"\nCreating LaTeX table (top {top_n})...")
    
    latex_content = []
    
    # Main table
    latex_content.append("\\begin{table}[htbp]")
    latex_content.append("\\centering")
    latex_content.append(f"\\caption{{Top {top_n} Features by Importance Methods}}")
    latex_content.append("\\label{tab:top_features}")
    
    # Column specification
    n_methods = len(methods)
    col_spec = "c" + "l" * n_methods
    latex_content.append(f"\\begin{{tabular}}{{{col_spec}}}")
    latex_content.append("\\hline")
    
    # Header
    header = "Rank & " + " & ".join([name for name, _ in methods.values()]) + " \\\\"
    latex_content.append(header)
    latex_content.append("\\hline")
    
    # Data rows (show first 20 or specified top_n)
    for _, row in pub_df.head(top_n).iterrows():
        values = [str(int(row['Rank']))] + [str(row[col]) if row[col] else '-' for col in methods.keys()]
        latex_content.append(" & ".join(values) + " \\\\")
    
    latex_content.append("\\hline")
    latex_content.append("\\end{tabular}")
    latex_content.append("\\end{table}")
    
    latex_str = "\n".join(latex_content)
    
    with open(f'top{top_n}_features_ranking_latex.tex', 'w') as f:
        f.write(latex_str)
    
    print(f"✓ Saved: top{top_n}_features_ranking_latex.tex")

def create_consensus_ranking(complete_df):
    """
    Create consensus ranking using only reliable methods
    """
    print("\n" + "="*80)
    print("CREATING CONSENSUS RANKING")
    print("="*80 + "\n")
    
    # Use only key metrics for consensus
    consensus_metrics = {
        'Pearson': 'abs_pearson',
        'Spearman': 'abs_spearman',
        'GradBoost_Perm': 'gradboost_perm_importance',
        'Avg_Perm': 'avg_perm_importance'
    }
    
    # Add XGBoost if available
    if 'xgboost_perm_importance' in complete_df.columns:
        consensus_metrics['XGBoost_Perm'] = 'xgboost_perm_importance'
    
    print(f"Using {len(consensus_metrics)} methods for consensus ranking:")
    for name, col in consensus_metrics.items():
        print(f"  - {name}")
    
    # Calculate ranks
    rank_df = complete_df[['feature', 'feature_group']].copy()
    
    for name, column in consensus_metrics.items():
        rank_df[f'{name}_rank'] = complete_df[column].rank(ascending=False, method='min')
    
    # Average rank
    rank_columns = [col for col in rank_df.columns if col.endswith('_rank')]
    rank_df['avg_rank'] = rank_df[rank_columns].mean(axis=1)
    rank_df['rank_std'] = rank_df[rank_columns].std(axis=1)
    
    # Sort by average rank
    rank_df = rank_df.sort_values('avg_rank')
    
    # Add original values
    for name, column in consensus_metrics.items():
        rank_df[column] = complete_df.set_index('feature').loc[rank_df['feature'], column].values
    
    # Save
    rank_df.to_csv('consensus_feature_ranking.csv', index=False)
    print("\n✓ Saved: consensus_feature_ranking.csv")
    
    # Print top 20
    print("\n" + "="*70)
    print("TOP 20 FEATURES BY CONSENSUS RANKING")
    print("="*70)
    
    top20 = rank_df.head(20)
    for i, (_, row) in enumerate(top20.iterrows(), 1):
        print(f"{i:2d}. {row['feature']:45s} | Avg Rank: {row['avg_rank']:5.1f} ± {row['rank_std']:4.1f}")
    
    return rank_df

def create_importance_comparison_plot(complete_df, top_n=20):
    """
    Create comprehensive comparison plot
    """
    print(f"\nCreating importance comparison plot (top {top_n})...")
    
    # Get consensus top features
    if 'avg_perm_importance' in complete_df.columns:
        top_features = complete_df.nlargest(top_n, 'avg_perm_importance')['feature'].tolist()
    else:
        top_features = complete_df.nlargest(top_n, 'abs_pearson')['feature'].tolist()
    
    # Select methods to plot
    methods_to_plot = {
        'Pearson Correlation': 'abs_pearson',
        'Spearman Correlation': 'abs_spearman',
        'GradBoost Perm': 'gradboost_perm_importance',
        'RF Importance': 'randomforest_importance',
        'ET Importance': 'extratrees_importance',
    }

    if 'xgboost_perm_importance' in complete_df.columns:
        methods_to_plot['XGBoost Perm'] = 'xgboost_perm_importance'

    if 'avg_perm_importance' in complete_df.columns:
        methods_to_plot['Avg Perm Imp'] = 'avg_perm_importance'
    
    # Filter data
    plot_data = complete_df[complete_df['feature'].isin(top_features)].copy()
    
    # Normalize each method to 0-1 for comparison
    for method_name, column in methods_to_plot.items():
        if column in plot_data.columns:
            plot_data[f'{method_name}_norm'] = (plot_data[column] - plot_data[column].min()) / (plot_data[column].max() - plot_data[column].min())
    
    # Create plot
    fig, axes = plt.subplots(2, 3, figsize=(20, 12))
    axes = axes.flatten()
    
    for idx, (method_name, column) in enumerate(methods_to_plot.items()):
        if idx >= len(axes):
            break
        
        ax = axes[idx]
        
        if column in plot_data.columns:
            sorted_data = plot_data.nlargest(top_n, column)
            
            ax.barh(range(len(sorted_data)), sorted_data[column], color='steelblue', alpha=0.7)
            ax.set_yticks(range(len(sorted_data)))
            ax.set_yticklabels(sorted_data['feature'], fontsize=9)
            ax.set_xlabel('Importance Score', fontweight='bold')
            ax.set_title(method_name, fontweight='bold', fontsize=14)
            ax.grid(True, alpha=0.3, axis='x')
            ax.invert_yaxis()
    
    # Remove empty subplots
    for idx in range(len(methods_to_plot), len(axes)):
        fig.delaxes(axes[idx])
    
    plt.suptitle(f'Feature Importance Comparison - Top {top_n} Features', 
                 fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.savefig(f'top{top_n}_importance_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✓ Saved: top{top_n}_importance_comparison.png")

def create_correlation_scatter(complete_df):
    """Create scatter plot of correlation vs permutation importance"""
    print("\nCreating correlation vs permutation importance scatter...")
    
    if 'avg_perm_importance' not in complete_df.columns:
        print("  Skipping - permutation importance not available")
        return
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Scatter plot
    scatter = ax.scatter(
        complete_df['abs_pearson'],
        complete_df['avg_perm_importance'],
        c=complete_df['abs_spearman'],
        cmap='viridis',
        alpha=0.6,
        s=50,
        edgecolors='white',
        linewidth=0.5
    )
    
    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Spearman Correlation', fontweight='bold')
    
    # Labels
    ax.set_xlabel('Absolute Pearson Correlation', fontweight='bold', fontsize=14)
    ax.set_ylabel('Average Permutation Importance', fontweight='bold', fontsize=14)
    ax.set_title('Feature Importance: Correlation vs Predictive Power', 
                 fontweight='bold', fontsize=16)
    ax.grid(True, alpha=0.3)
    
    # Annotate top 10
    top10 = complete_df.nlargest(10, 'avg_perm_importance')
    for _, row in top10.iterrows():
        ax.annotate(
            row['feature'],
            (row['abs_pearson'], row['avg_perm_importance']),
            xytext=(5, 5),
            textcoords='offset points',
            fontsize=8,
            alpha=0.7
        )
    
    plt.tight_layout()
    plt.savefig('correlation_vs_permutation_scatter.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print("✓ Saved: correlation_vs_permutation_scatter.png")

def main(transformation='raw', remove_outliers=False, outlier_percentile=6):
    """
    Main execution

    Parameters:
    -----------
    transformation : str, default='raw'
        Type of transformation: 'raw', 'sqrt', 'log', 'log1p'
    remove_outliers : bool, default=False
        Whether to remove outliers
    outlier_percentile : float, default=6
        Percentile for outlier removal
    """
    print("="*80)
    print("FEATURE IMPORTANCE ANALYSIS FOR PUBLICATION")
    print("Focus: Correlations + Permutation Importance (Most Reliable)")
    print("Models: Gradient Boosting, XGBoost, Random Forest, Extra Trees")
    print(f"Transformation: {transformation.upper()}")
    print(f"Outlier Removal: {remove_outliers}")
    print("="*80)

    # Create suffix for file names
    suffix = f"_{transformation}"
    if remove_outliers:
        suffix += f"_no_outliers_{100-2*outlier_percentile}pct"

    # Load data
    X_train, y_train, X_test, y_test = load_and_prepare_data(
        transformation=transformation,
        remove_outliers=remove_outliers,
        outlier_percentile=outlier_percentile
    )

    # Create feature groups
    feature_to_group = create_feature_groups(X_train.columns)

    # Create preprocessor
    preprocessor = create_preprocessor(X_train)

    # Compute importance metrics
    complete_df = compute_feature_importance_for_paper(
        X_train, y_train, X_test, y_test,
        preprocessor, feature_to_group
    )

    # Save complete results
    complete_df.to_csv(f'complete_feature_importance_metrics{suffix}.csv', index=False)
    complete_df.to_excel(f'complete_feature_importance_metrics{suffix}.xlsx', index=False, engine='openpyxl')
    print(f"\n✓ Saved: complete_feature_importance_metrics{suffix}.csv/.xlsx")

    # Create publication ranking table
    ranking_df, pub_df = create_publication_ranking_table(complete_df, top_n=20)

    # Rename files with suffix
    import os
    for old_file in ['top20_features_ranking_publication.csv',
                     'top20_features_ranking_publication.xlsx',
                     'top20_features_ranking_latex.tex',
                     'top20_features_ranking_with_values.csv']:
        if os.path.exists(old_file):
            base, ext = os.path.splitext(old_file)
            new_file = f"{base}{suffix}{ext}"
            os.rename(old_file, new_file)

    # Create consensus ranking
    consensus_df = create_consensus_ranking(complete_df)
    if os.path.exists('consensus_feature_ranking.csv'):
        os.rename('consensus_feature_ranking.csv', f'consensus_feature_ranking{suffix}.csv')

    # Create visualizations
    create_importance_comparison_plot(complete_df, top_n=20)
    for old_file in ['top20_importance_comparison.png']:
        if os.path.exists(old_file):
            base, ext = os.path.splitext(old_file)
            new_file = f"{base}{suffix}{ext}"
            os.rename(old_file, new_file)

    create_correlation_scatter(complete_df)
    for old_file in ['correlation_vs_permutation_scatter.png']:
        if os.path.exists(old_file):
            base, ext = os.path.splitext(old_file)
            new_file = f"{base}{suffix}{ext}"
            os.rename(old_file, new_file)

    # Print summary
    print("\n" + "="*80)
    print(f"FILES GENERATED FOR PUBLICATION ({transformation.upper()})")
    print("="*80)

    print("\n=== MAIN RANKING TABLES ===")
    print(f"✓ top20_features_ranking_publication{suffix}.csv/.xlsx")
    print(f"✓ top20_features_ranking_latex{suffix}.tex")
    print(f"✓ consensus_feature_ranking{suffix}.csv")

    print("\n=== COMPLETE DATA ===")
    print(f"✓ complete_feature_importance_metrics{suffix}.csv/.xlsx")
    print(f"✓ top20_features_ranking_with_values{suffix}.csv")

    print("\n=== VISUALIZATIONS ===")
    print(f"✓ top20_importance_comparison{suffix}.png")
    print(f"✓ correlation_vs_permutation_scatter{suffix}.png")

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE!")
    print("="*80)

    return complete_df, ranking_df, consensus_df

if __name__ == "__main__":
    # Run with RAW values (no transformation, no outlier removal)
    print("\n" + "#"*80)
    print("### ANALYSIS 1: RAW VALUES (NO TRANSFORMATION)")
    print("#"*80 + "\n")
    complete_df_raw, ranking_df_raw, consensus_df_raw = main(
        transformation='raw',
        remove_outliers=False
    )

    # Run with LOG transformation (no outlier removal)
    print("\n\n" + "#"*80)
    print("### ANALYSIS 2: LOG TRANSFORMATION")
    print("#"*80 + "\n")
    complete_df_log, ranking_df_log, consensus_df_log = main(
        transformation='log',
        remove_outliers=False
    )

    # Run with LOG1P transformation (no outlier removal)
    print("\n\n" + "#"*80)
    print("### ANALYSIS 3: LOG1P TRANSFORMATION")
    print("#"*80 + "\n")
    complete_df_log1p, ranking_df_log1p, consensus_df_log1p = main(
        transformation='log1p',
        remove_outliers=False
    )

    print("\n\n" + "="*80)
    print("ALL ANALYSES COMPLETE!")
    print("="*80)
    print("\nGenerated 3 complete sets of files:")
    print("  1. *_raw.* - Raw values, no transformation")
    print("  2. *_log.* - Natural log transformation")
    print("  3. *_log1p.* - Log(1+x) transformation")
    print("\nCompare the results to choose the best approach for your paper!")
    print("="*80)