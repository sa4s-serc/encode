# EnCoDe Dataset Documentation

This document describes the dataset released alongside the EnCoDe paper. The dataset contains static code features and measured energy consumption for 8,358 Python code blocks extracted from real-world programs.

---

## Summary

| Property | Value |
|----------|-------|
| Total blocks | 8,358 (train: 6,686 / test: 1,672) |
| Source programs | 18,612 Python files |
| Source | HuggingFace — `iamtarun/python_code_instructions_18k_alpaca` |
| Features per block | 33 static AST metrics |
| Energy range | 2.37×10⁻⁵ J — 7.48×10² J (6 orders of magnitude) |
| Measurement hardware | Intel i7-6700K, Pop!_OS 22.04 LTS |
| Measurement tool | PowerLens (see `PowerLens/README.md`) |

---

## Files

All files live in `modeling_results/`:

| File | Rows | Columns | Description |
|------|------|---------|-------------|
| `X_train_base_features.csv` | 6,686 | 33 + index | Training feature matrix |
| `X_test_base_features.csv` | 1,672 | 33 + index | Test feature matrix |
| `target_variables.csv` | 8,358 | 6 + index | Energy labels (train + test, raw + log-transformed) |

### `target_variables.csv` columns

| Column | Description |
|--------|-------------|
| `energy_train` | Measured energy in Joules for training blocks (NaN for test rows) |
| `energy_test` | Measured energy in Joules for test blocks (NaN for train rows) |
| `categories_train` | Tier label — Low / Medium / High (train rows) |
| `categories_test` | Tier label — Low / Medium / High (test rows) |
| `log_energy_train` | Natural-log of `energy_train` |
| `log_energy_test` | Natural-log of `energy_test` |

**Tier boundaries** are defined by equal-frequency binning on the training set:
- **Low** — energy ≤ 33rd percentile
- **Medium** — 33rd to 67th percentile
- **High** — above 67th percentile

---

## Block Types

Blocks were extracted from the following Python AST node types:

| Type | Description |
|------|-------------|
| `FunctionDef` | Function definition (`def`) |
| `For` | For loop |
| `While` | While loop |
| `If` | If statement (including elif/else branches) |
| `Try` | Try-except block |
| `With` | With statement (context manager) |

Blocks executing in under 1 µs were excluded (insufficient RAPL signal).

---

## Feature Schema

All 33 feature columns follow the naming convention `feature_<name>`. Each represents a static property computed from the block's AST without executing the code.

### Structural Features (5)

| Feature | Description |
|---------|-------------|
| `feature_total_nodes` | Total number of AST nodes in the block |
| `feature_unique_node_types` | Number of distinct AST node type categories |
| `feature_max_depth` | Maximum depth of the AST tree |
| `feature_avg_depth` | Mean depth of all leaf nodes |
| `feature_depth_variance` | Variance of leaf-node depths |

### Complexity Features (4)

| Feature | Description |
|---------|-------------|
| `feature_cyclomatic_complexity` | McCabe cyclomatic complexity (branches + 1) |
| `feature_cognitive_complexity` | Cognitive complexity (nesting-weighted branch count) |
| `feature_nesting_complexity` | Maximum nesting depth of control structures |
| `feature_control_flow_complexity` | Total control-flow decision points |

### Density Features (5)

| Feature | Description |
|---------|-------------|
| `feature_operator_density` | Operators per AST node |
| `feature_literal_density` | Literal values per AST node |
| `feature_call_density` | Function call nodes per AST node |
| `feature_variable_density` | Variable references per AST node |
| `feature_attribute_density` | Attribute accesses per AST node |

### Entropy / Diversity Features (3)

| Feature | Description |
|---------|-------------|
| `feature_node_type_entropy` | Shannon entropy of AST node type distribution |
| `feature_operator_entropy` | Shannon entropy over operator types |
| `feature_variable_entropy` | Shannon entropy over variable identifiers |

### Unique Count Features (3)

| Feature | Description |
|---------|-------------|
| `feature_unique_variables` | Number of distinct variable names |
| `feature_unique_operators` | Number of distinct operator types |
| `feature_unique_functions` | Number of distinct function names called |

### Structural Ratio Features (3)

| Feature | Description |
|---------|-------------|
| `feature_avg_branching_factor` | Mean number of children per non-leaf AST node |
| `feature_max_branching_factor` | Maximum children count across all nodes |
| `feature_leaves_to_nodes_ratio` | Fraction of AST nodes that are leaves |

### Code Pattern Counts (5)

| Feature | Description |
|---------|-------------|
| `feature_loops_count` | Total for + while loops |
| `feature_conditionals_count` | Total if / elif / else branches |
| `feature_functions_count` | Function definitions inside the block |
| `feature_classes_count` | Class definitions inside the block |
| `feature_try_blocks_count` | Try-except constructs |

### Halstead Metrics (5)

Derived from Halstead's software science theory, computed over the block's operators and operands.

| Feature | Description |
|---------|-------------|
| `feature_vocabulary_size` | Unique operators + unique operands |
| `feature_program_length` | Total operator occurrences + total operand occurrences |
| `feature_program_volume` | `program_length × log₂(vocabulary_size)` |
| `feature_program_difficulty` | `(unique_operators / 2) × (total_operands / unique_operands)` |
| `feature_program_effort` | `program_volume × program_difficulty` |

---

## Measurement Methodology

Energy labels were produced by **PowerLens** — a novel measurement tool developed as part of this research. Key mechanisms:

1. **Environmental Stabilization** — CPU frequency locked via `cpufreq` governor, Turbo Boost disabled, process pinned to a single core.
2. **Execution Amplification** — each block is repeated N times (typically 1,000–10,000×) so the cumulative energy exceeds RAPL's ~1 ms update granularity.
3. **Temporal Synchronization** — execution is aligned to RAPL counter update boundaries to avoid partial-window reads.
4. **Calibrated Subtraction** — overhead of the repetition loop itself is measured and subtracted.
5. **Statistical Aggregation** — 10 independent trials; IQR-based outlier removal; mean of retained trials reported.

For full methodology details see [PowerLens/README.md](PowerLens/README.md) and the paper.

---

## Loading the Dataset

```python
import pandas as pd

X_train = pd.read_csv('modeling_results/X_train_base_features.csv', index_col=0)
X_test  = pd.read_csv('modeling_results/X_test_base_features.csv',  index_col=0)
targets = pd.read_csv('modeling_results/target_variables.csv',       index_col=0)

y_train = targets.loc[X_train.index, 'energy_train']
y_test  = targets.loc[X_test.index,  'energy_test']

print(X_train.shape)   # (6686, 33)
print(y_train.describe())
```

---

## Training Your Own Model

```python
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import numpy as np

# Load
X_train = pd.read_csv('modeling_results/X_train_base_features.csv', index_col=0)
targets = pd.read_csv('modeling_results/target_variables.csv', index_col=0)
y_train = targets.loc[X_train.index, 'energy_train']

# Train (sqrt transform improves regression on this skewed target)
pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('model',  GradientBoostingRegressor(n_estimators=250, max_depth=6, random_state=42))
])
pipeline.fit(X_train, np.sqrt(y_train))

# Predict (remember to invert the transform)
y_pred = pipeline.predict(X_test) ** 2
```

The model training script used in the paper is at [WattWise-main/python/train_and_save_models.py](WattWise-main/python/train_and_save_models.py).

---

## Citing This Dataset

If you use this dataset in your research, please cite the EnCoDe paper:

```bibtex
@misc{goyal2026encodeenergyestimationsource,
      title={EnCoDe: Energy Estimation of Source Code At Design-Time}, 
      author={Shailender Goyal and Akhila Matathammal and Karthik Vaidhyanathan},
      year={2026},
      eprint={2605.00504},
      archivePrefix={arXiv},
      primaryClass={cs.SE},
      url={https://arxiv.org/abs/2605.00504}, 
}
```

---

## Limitations

- **Platform** — measurements were taken on a single machine (Intel i7-6700K, Linux). Energy values for the same code will differ on other hardware.
- **Language** — only Python 3 is covered. The feature extractor is Python-AST specific.
- **Scope** — RAPL measures package energy (CPU + integrated GPU + DRAM on some platforms); disk and network I/O are not captured. Blocks that are primarily I/O-bound may not be well-represented.
- **Execution amplification** — blocks that modify shared state across repetitions required isolation wrappers; a small fraction of blocks were excluded if isolation was not feasible.
