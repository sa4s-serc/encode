# EnCoDe: Energy Estimation of Source Code At Design-Time

> **Paper accepted at EASE 2026** — *EnCoDe: Energy Estimation of Source Code At Design-Time*
> Shailender Goyal, Akhila Matathammal, Karthik Vaidhyanathan — IIIT Hyderabad
> [ACM Digital Library](https://camps.aptaracorp.com/ACM_PMS/PMS/ACM/EASE26/49/4ff498d9-568f-11f1-b513-16ffd757ba29/OUT/ease26-49.html) | [arXiv](https://arxiv.org/abs/2605.00504)

Existing energy profiling tools require code to run and report only coarse process-level consumption. **EnCoDe** closes this gap: it predicts the energy footprint of Python code blocks *statically*, before execution, directly inside the IDE.

The system has three interlocking parts:

1. **PowerLens** — a novel measurement methodology that reliably measures sub-millisecond block-level energy on Linux/Intel hardware by combining execution amplification, temporal synchronization with RAPL counters, and IQR-based statistical aggregation.
2. **Dataset** — 14,358 Python code blocks (functions, loops, conditionals, etc.) extracted from 18,612 real-world programs, each measured with PowerLens, spanning six orders of magnitude in energy (2.37×10⁻⁵ J – 7.48×10² J).
3. **WattWise** — a VS Code extension that runs ML models (Gradient Boosting + XGBoost) on 33 static AST features to predict energy *without running the code*, shows inline decorations, and offers AI-powered optimization suggestions via Gemini 2.5 Flash.

---

## Key Results

| Task | Model | Metric | Score |
|------|-------|--------|-------|
| Energy regression | Gradient Boosting | Test R² | **0.755** |
| Tier classification (Low/Med/High) | XGBoost | Test Accuracy | **80.6%** |
| Tier classification | XGBoost | Test F1 | **0.805** |

Ablation study confirms that the full 33-feature set outperforms size-only baselines by 23+ percentage points in accuracy.

---

## Repository Structure

```
EnCoDe/
├── PowerLens/                  Measurement methodology (Python + C extension)
│   ├── powerlens.py            High-level API (context managers, decorators)
│   ├── _powerlens_core.c       Low-level RAPL access via MSR / powercap
│   ├── setup.py                Build the C extension
│   └── README.md               Full PowerLens documentation
│
├── WattWise-main/              VS Code extension + dashboard + GitHub bot
│   ├── src/                    TypeScript extension source
│   ├── python/                 ML backend (feature extraction, prediction, training)
│   │   ├── requirements.txt    Python dependencies
│   │   ├── extract_features.py AST → 33 static metrics
│   │   ├── predict_energy.py   Runs trained models
│   │   ├── train_and_save_models.py  Retrain on your own data
│   │   ├── suggest_improvements.py  Gemini AI suggestions
│   │   └── models/             Pre-trained .joblib model files
│   ├── dashboard/              FastAPI + React repo-wide analysis dashboard
│   ├── wattwise-bot/           GitHub Actions PR bot with manager approval
│   ├── package.json            VS Code extension manifest
│   └── README.md               WattWise setup & usage guide
│
├── modeling_results/           Training/test CSVs, ablation study, feature importance
│   ├── X_train_base_features.csv
│   ├── X_test_base_features.csv
│   ├── target_variables.csv
│   └── ablation_study.py
│
├── Misc/
│   └── powerlens_pyrapl_raw_data/  Validation data comparing PowerLens vs PyRAPL
│
├── Paper/                      LaTeX source for the EASE 2026 paper
├── DATASET.md                  Dataset documentation and feature schema
└── EASE_2025_GreenSoftware-1.pdf   Full paper (pre-print)
```

---

## Quick Start

### Run the WattWise VS Code Extension

See [WattWise-main/README.md](WattWise-main/README.md) for full setup.

**TL;DR with pre-trained models:**
```bash
cd WattWise-main
npm install && npm run compile
# Open in VS Code → F5 → open any .py file → right-click → Analyze Energy Consumption
```

### Use PowerLens for Measurement

See [PowerLens/README.md](PowerLens/README.md). Requires Linux + Intel RAPL.

```bash
cd PowerLens
python setup.py build_ext --inplace
```

```python
from powerlens import measure_energy

with measure_energy() as m:
    result = [x**2 for x in range(10000)]

print(f"Energy: {m.energy_joules:.4e} J")
```

### Explore the Dataset

See [DATASET.md](DATASET.md) for the full feature schema and dataset statistics.

```python
import pandas as pd

X_train = pd.read_csv('modeling_results/X_train_base_features.csv', index_col=0)
targets = pd.read_csv('modeling_results/target_variables.csv', index_col=0)
print(X_train.shape)   # (6686, 33)
```

---

## How It Works

```
Python source file
       │
       ▼
  [AST Parser]  ─── identifies def / for / while / if / try / with blocks
       │
       ▼
  [extract_features.py]  ─── 33 static metrics per block
  (complexity, density, Halstead, structural, pattern counts)
       │
       ▼
  [predict_energy.py]
       ├── GradientBoostingRegressor  →  energy in Joules (R²=0.755)
       └── XGBoostClassifier          →  Low / Medium / High tier (80.6% acc)
       │
       ▼
  VS Code inline decorations  ⚡ 1.23e-03 J · Medium
  + hover tooltips + AI suggestions for High-energy blocks
```

Ground-truth labels were produced by **PowerLens**: each code block was executed thousands of times in a controlled Linux environment, with RAPL energy readings time-aligned to update boundaries and IQR outlier removal applied across 10 trials.

---

## Reproducibility

To retrain the models from the released dataset:

```bash
cd WattWise-main/python
pip install -r requirements.txt

# copy dataset files
cp ../../modeling_results/X_train_base_features.csv data/
cp ../../modeling_results/X_test_base_features.csv  data/
cp ../../modeling_results/target_variables.csv       data/

python train_and_save_models.py
# → writes gradient_boosting_regressor.joblib, xgboost_classifier.joblib to models/
```

To reproduce the ablation study from the paper:

```bash
cd modeling_results
python ablation_study.py
```

---

## Citation

If you use EnCoDe, WattWise, PowerLens, or the dataset in your research, please cite:

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
}
```

---

## License

This repository is released for research and non-commercial use.
Contact: shailender.goyal@research.iiit.ac.in
