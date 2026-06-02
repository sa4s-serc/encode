# WattWise — Energy Linter for Python

WattWise is a VS Code extension that estimates the energy footprint of Python code blocks *at design time* — no execution required. It uses ML models trained on 14,000+ real measurements to show energy estimates and tier classifications (Low / Medium / High) as inline decorations, and calls Gemini 2.5 Flash to suggest concrete optimizations for high-energy blocks.

WattWise is the developer-facing component of the [EnCoDe](../README.md) research project (EASE 2026).

---

## Features

- **Inline energy estimates** — `⚡ 1.23e-03 J · Medium` shown at the end of every analyzed block
- **Tier classification** — Low / Medium / High based on the distribution of the training dataset
- **Hover tooltips** — block type, precise energy value, confidence score, recommendations
- **AI suggestions** — Gemini 2.5 Flash explains *why* a block is energy-intensive and proposes rewrites
- **Repo-wide dashboard** — FastAPI + React UI to scan an entire repository and track energy trends over time
- **GitHub PR bot** — automatically comments on PRs with energy regressions and requests manager approval when thresholds are exceeded

---

## Architecture

```
VS Code Extension (TypeScript)
  └── pythonBridge.ts  — spawns Python subprocesses, parses JSON output
        ├── extract_features.py     AST → 33 static metrics
        ├── predict_energy.py       loads .joblib models → energy (J) + tier
        └── suggest_improvements.py Gemini 2.5 Flash → actionable rewrites

Dashboard (optional, standalone)
  ├── dashboard/backend/   FastAPI — repo scan, SQLite history, cost estimates
  └── dashboard/frontend/  React + Vite — interactive charts and file browser

GitHub PR Bot (optional)
  └── wattwise-bot/        Python bot triggered by GitHub Actions
        ├── diff_analyser.py  energy delta for changed blocks
        ├── comment_builder.py PR comment with block breakdown + cost impact
        └── github_api.py     posts comments, sets status checks
```

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.8+ | used by the ML backend |
| Node.js | 18+ | needed to compile the extension |
| npm | 8+ | bundled with Node.js |
| VS Code | 1.75+ | target IDE |
| Gemini API key | — | *optional*, only for AI suggestions |

---

## Setup: Extension (Pre-trained Models — Recommended)

The `python/models/` directory ships with pre-trained models. No dataset or training step needed.

**1. Install Python dependencies**

```bash
cd WattWise-main/python
pip install -r requirements.txt
```

If you don't need AI suggestions, omit `google-genai`:

```bash
pip install pandas numpy scikit-learn xgboost joblib
```

**2. Install Node dependencies and compile**

```bash
cd WattWise-main
npm install
npm run compile
```

**3. Launch the extension in VS Code**

- Open the `WattWise-main` folder in VS Code
- Press `F5` — a new Extension Development Host window opens with WattWise active

Or install directly from the pre-built package:

```bash
code --install-extension energy-estimator-1.0.0.vsix
```

**4. Analyze a Python file**

Open any `.py` file, then use any of:

- Right-click in the editor → **WattWise: Analyze Energy Consumption**
- Command Palette (`Ctrl+Shift+P`) → **WattWise: Analyze Energy Consumption**
- Click the `⚡` icon in the editor title bar (appears automatically for `.py` files)

Energy estimates appear as inline decorations at the end of each block.

---

## Setup: Retrain Models on Your Own Data

Use this path if you have collected new energy measurements or want to experiment with different features.

**1. Prepare the dataset**

Place the following CSV files in `WattWise-main/python/data/`:

| File | Description |
|------|-------------|
| `X_train_base_features.csv` | Training features (index + 33 columns) |
| `X_test_base_features.csv` | Test features |
| `target_variables.csv` | Energy labels (`energy_train`, `energy_test` columns) |

The dataset released with this repository lives in `../modeling_results/` — copy from there:

```bash
mkdir -p WattWise-main/python/data
cp modeling_results/X_train_base_features.csv WattWise-main/python/data/
cp modeling_results/X_test_base_features.csv  WattWise-main/python/data/
cp modeling_results/target_variables.csv       WattWise-main/python/data/
```

**2. Run training**

```bash
cd WattWise-main/python
python train_and_save_models.py
```

Training takes under 2 minutes on a modern laptop. It prints R² (regression) and accuracy (classification) and writes four files to `python/models/`:

```
models/
├── gradient_boosting_regressor.joblib   energy prediction in Joules
├── xgboost_classifier.joblib            Low / Medium / High classifier
├── label_encoder.joblib                 maps numeric labels ↔ tier names
└── model_metadata.json                  feature names, energy boundaries, metrics
```

**3. Reload the extension** — VS Code picks up the new models on the next analysis run.

---

## Setup: Dashboard

The dashboard scans an entire repository, stores results in SQLite, and estimates annual energy cost.

```bash
cd WattWise-main/dashboard

# Backend
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev       # opens at http://localhost:5173
```

Point the UI at any local Python repository. Results persist across sessions in `dashboard/data/wattwise.db`.

---

## Setup: GitHub PR Bot

The bot posts an energy report as a PR comment every time Python files change.

**1. Copy the workflow to your target repository**

```bash
cp WattWise-main/.github/workflows/wattwise-pr.yml  YOUR_REPO/.github/workflows/
cp WattWise-main/wattwise-bot/                      YOUR_REPO/wattwise-bot/
cp WattWise-main/python/                            YOUR_REPO/python/
```

**2. Add `.wattwise.yml` to your repository root**

```yaml
energy:
  require_manager_approval: true   # block merge if high-energy blocks added
  max_new_high_blocks: 0           # zero tolerance for new High-tier blocks
  regression_threshold_cost: 500   # annual cost threshold in ₹ before approval required
  block_on_gate_failure: true

managers:
  - YourGitHubUsername

cost:
  rate_kwh: 8.0                    # electricity rate (₹/kWh — adjust for your region)
  default_calls_per_day:
    FunctionDef: 10000
    For: 50000
    While: 20000
    If: 100000
    Try: 5000
    With: 10000
```

**3. `GITHUB_TOKEN`** is auto-provided by Actions — no secret configuration needed.

---

## Configuration

All settings are under the `wattwise` namespace in VS Code settings (`Ctrl+,`):

| Setting | Default | Description |
|---------|---------|-------------|
| `wattwise.pythonPath` | `python3` | Path to the Python interpreter |
| `wattwise.showInlineDecorations` | `true` | Show energy estimates inline |
| `wattwise.showHoverInfo` | `true` | Show detailed info on hover |
| `wattwise.decorationFormat` | `⚡ {energy}J · {tier}` | Format string; `{energy}` and `{tier}` are placeholders |
| `wattwise.geminiApiKey` | *(empty)* | Gemini API key for AI suggestions (free at [aistudio.google.com](https://aistudio.google.com/app/apikey)) |

You can also set the key via an environment variable or a `.env` file in the extension root:

```
GEMINI_API_KEY=your_key_here
```

---

## Commands

| Command ID | Menu Label | Description |
|------------|-----------|-------------|
| `wattwise.analyzeFile` | WattWise: Analyze Energy Consumption | Run analysis on the current `.py` file |
| `wattwise.clearAnalysis` | WattWise: Clear Energy Analysis | Remove inline decorations |
| `wattwise.trainModels` | WattWise: Train Energy Prediction Models | Retrain models from `python/data/` |

---

## Reading Results

**Inline decorations** (end of each block):

```python
def compute_scores(data):          # ⚡ 3.41e-04 J · Low
    for item in data:              # ⚡ 1.87e-03 J · Medium
        results.append(item * 2)
```

**Hover tooltip** shows:
- Block type and line range
- Energy value in Joules (precise)
- Tier (Low / Medium / High) with confidence score
- Recommendations (e.g., "Consider vectorizing this loop with NumPy")
- AI-suggested rewrite (if Gemini key is configured and tier is High)

**Output panel** (WattWise channel) shows:
- Total blocks analyzed and total energy
- Tier distribution
- Per-block breakdown sorted by energy descending
- Optimization recommendations

---

## How the Models Work

### Feature Extraction

For each code block, `extract_features.py` parses the AST and computes 33 static metrics:

| Category | Features |
|----------|---------|
| Structural (5) | `total_nodes`, `unique_node_types`, `max_depth`, `avg_depth`, `depth_variance` |
| Complexity (4) | `cyclomatic_complexity`, `cognitive_complexity`, `nesting_complexity`, `control_flow_complexity` |
| Density (5) | `operator_density`, `literal_density`, `call_density`, `variable_density`, `attribute_density` |
| Entropy (3) | `node_type_entropy`, `operator_entropy`, `variable_entropy` |
| Halstead (5) | `vocabulary_size`, `program_length`, `program_volume`, `program_difficulty`, `program_effort` |
| Unique counts (3) | `unique_variables`, `unique_operators`, `unique_functions` |
| Pattern counts (5) | `loops_count`, `conditionals_count`, `functions_count`, `classes_count`, `try_blocks_count` |
| Structural ratios (3) | `branching_factor`, `leaf_to_node_ratio`, `avg_children_per_node` |

### Prediction Pipeline

```
Feature vector (33 values)
  → ColumnTransformer (StandardScaler / RobustScaler / MinMaxScaler by feature group)
  → GradientBoostingRegressor (n_estimators=250, max_depth=6, lr=0.06)
  → sqrt inverse transform
  → energy in Joules

Feature vector (33 values)
  → same ColumnTransformer
  → XGBoostClassifier (n_estimators=250, max_depth=6, lr=0.08)
  → Low / Medium / High + confidence score
```

### Model Performance

| Model | Train | Test | Gap |
|-------|-------|------|-----|
| GBR regression R² | 0.81 | 0.755 | 0.055 |
| XGBoost accuracy | 0.84 | 0.806 | 0.034 |
| XGBoost F1 (weighted) | — | 0.805 | — |

---

## Scaling

**Single-file analysis** runs in under one second for files up to a few thousand lines. The Python subprocess is spawned once per analysis and exits cleanly.

**Repo-wide dashboard** — `dashboard/backend/scanner.py` walks the repository and distributes block extraction across a `concurrent.futures.ThreadPoolExecutor`. A 500-file repository typically completes in 10–30 seconds on a modern laptop.

**GitHub CI** — the PR bot runs only on *changed* Python files (not the full repo), so CI time scales with the size of the diff, not the repository.

**Retraining** — `train_and_save_models.py` is a one-shot offline step. XGBoost uses `n_jobs=-1` (all cores). On the 8,358-sample dataset it completes in under 2 minutes on any modern machine. If you collect a much larger dataset, consider switching to the `hist` tree method in XGBoost for faster training.

**Hardware limits for measurement** — PowerLens (energy data collection) requires Linux with an Intel CPU that supports RAPL (Sandy Bridge or newer) and access to `/sys/class/powercap/intel-rapl` or `/dev/cpu/*/msr`. The WattWise extension and dashboard are fully cross-platform; they use only the pre-trained models and do not require RAPL.

**Extending to other languages** — the feature extractor is Python-AST specific. To support another language, implement a new `extract_features_<lang>.py` that produces the same 33-column JSON output. The prediction and training pipeline downstream is language-agnostic.

---

## Project Structure

```
WattWise-main/
├── src/
│   ├── extension.ts          VS Code extension entry point
│   ├── pythonBridge.ts       spawns Python subprocesses, handles IPC
│   ├── decorations.ts        inline decoration rendering
│   └── webviewPanel.ts       webview-based report panel
├── python/
│   ├── requirements.txt      Python dependencies
│   ├── extract_features.py   AST feature extraction
│   ├── predict_energy.py     energy prediction using trained models
│   ├── train_and_save_models.py  offline model training
│   ├── suggest_improvements.py   Gemini AI suggestion engine
│   └── models/               pre-trained model files (committed)
│       ├── gradient_boosting_regressor.joblib
│       ├── xgboost_classifier.joblib
│       ├── label_encoder.joblib
│       └── model_metadata.json
├── dashboard/
│   ├── backend/              FastAPI server (scan, history, cost)
│   ├── frontend/             React + Vite UI
│   └── requirements.txt
├── wattwise-bot/
│   ├── src/                  GitHub bot logic
│   ├── requirements.txt
│   └── Dockerfile
├── .github/workflows/
│   └── wattwise-pr.yml       GitHub Actions workflow
├── .wattwise.yml             per-repo bot configuration
├── package.json              VS Code extension manifest
├── tsconfig.json
├── build_vsix.py             VSIX packaging helper
└── test_sample.py            sample Python file for manual testing
```

---

## Troubleshooting

**"Models not found" error**

The `python/models/` directory is committed with pre-trained models. If it is empty (e.g., after a shallow clone), run:

```bash
cd python && python train_and_save_models.py
```

**"Feature extraction failed"**

- Check that the file has valid Python 3 syntax (`python -m py_compile yourfile.py`)
- Ensure `wattwise.pythonPath` points to a working Python 3.8+ interpreter
- Check the WattWise Output channel for the raw error message

**Missing Python packages**

```bash
pip install pandas numpy scikit-learn xgboost joblib
```

**Extension not activating**

- The extension activates only on `.py` files — make sure the file is saved with a `.py` extension
- Reload the window: `Ctrl+Shift+P` → *Developer: Reload Window*
- Check for errors: `Ctrl+Shift+P` → *Developer: Toggle Developer Tools*

**Gemini suggestions not appearing**

- Set `wattwise.geminiApiKey` in VS Code settings (or `GEMINI_API_KEY` env var)
- Suggestions are generated only for **High**-tier blocks to keep API costs low
- The `google-genai` package must be installed: `pip install google-genai`

---

## Building for Distribution

```bash
npm run compile
npm install -g @vscode/vsce
vsce package
# produces wattwise-1.0.0.vsix
```

Install on any machine:

```bash
code --install-extension wattwise-1.0.0.vsix
```

---

> **Note:** WattWise provides *estimates* based on static code analysis. Actual energy consumption varies with hardware, runtime conditions, input data, and system load. For ground-truth profiling on Linux, use [PowerLens](../PowerLens/README.md).
