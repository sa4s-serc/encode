# Quick Start Guide

Get the Energy Estimator extension running in 5 minutes!

## Prerequisites

- Python 3.8+
- Node.js 18+
- VS Code

## Step-by-Step Setup

### 1. Run the Setup Script

```bash
cd /energy-estimator-vscode
./setup.sh
```

This will:
- ✓ Check dependencies
- ✓ Install Python packages
- ✓ Install Node packages
- ✓ Copy training data
- ✓ Train ML models
- ✓ Compile TypeScript

**Answer 'y' when asked to train models** (this takes 2-5 minutes).

### 2. Launch the Extension

**Option A: Debug Mode (Development)**
1. Open the extension folder in VS Code:
   ```bash
   code .
   ```
2. Press `F5` to launch Extension Development Host
3. A new VS Code window opens with the extension active

**Option B: Install as Package**
1. Package the extension:
   ```bash
   npm install -g vsce
   vsce package
   ```
2. Install the `.vsix` file:
   ```bash
   code --install-extension energy-estimator-1.0.0.vsix
   ```

### 3. Test It Out

1. In the new VS Code window, open `test_sample.py` (included in the extension folder)
2. Right-click anywhere in the file
3. Select **"Analyze Energy Consumption"**
4. Wait a few seconds...
5. See energy estimates appear inline! 🎉

### 4. View Results

**Inline Decorations:**
```python
def bubble_sort(arr):  # [Est: 2.34e-03J | Tier: High]
    for i in range(n):  # [Est: 5.67e-04J | Tier: Medium]
```

**Hover Tooltips:**
- Hover over any code block to see:
  - Detailed energy value
  - Tier classification
  - Confidence score
  - Recommendations

**Output Panel:**
- View → Output → Select "Energy Estimator"
- See complete analysis summary

## Common Issues

### "Models not found"
**Fix:** Run training:
```bash
cd python
python3 train_and_save_models.py
```

### "Training data not found"
**Fix:** Copy CSV files to `data/` folder:
```bash
cp ../X_train_base_features.csv data/
cp ../X_test_base_features.csv data/
cp ../target_variables.csv data/
```

### Python packages missing
**Fix:**
```bash
pip3 install pandas numpy scikit-learn xgboost joblib
```

### Extension won't compile
**Fix:**
```bash
npm install
npm run compile
```

## Next Steps

- Try analyzing your own Python files
- Adjust settings: `Ctrl+,` → Search "Energy Estimator"
- Check the full [README.md](README.md) for advanced features

## File Structure Overview

```
energy-estimator-vscode/
├── python/
│   ├── train_and_save_models.py   # Run once to train models
│   ├── extract_features.py        # Called by extension
│   ├── predict_energy.py          # Called by extension
│   └── models/                    # Generated after training
│       ├── gradient_boosting_regressor.joblib
│       ├── xgboost_classifier.joblib
│       └── model_metadata.json
├── data/                           # Place your CSV files here
│   ├── X_train_base_features.csv
│   ├── X_test_base_features.csv
│   └── target_variables.csv
├── src/                            # Extension source (TypeScript)
├── out/                            # Compiled JavaScript (generated)
└── test_sample.py                  # Sample file for testing
```

## Quick Command Reference

| Command | What it does |
|---------|-------------|
| `./setup.sh` | Full automated setup |
| `npm run compile` | Compile TypeScript |
| `F5` (in VS Code) | Launch extension in debug mode |
| `Ctrl+Shift+P` → "Energy: Analyze..." | Analyze current file |
| `python3 train_and_save_models.py` | Retrain models |

## Keyboard Shortcuts (once installed)

- No default shortcuts, but you can add them in VS Code:
  - `Ctrl+Shift+P` → "Preferences: Open Keyboard Shortcuts"
  - Search for "Energy"
  - Add your preferred shortcuts

## That's It!

You're ready to analyze energy consumption in your Python code! 🚀

For more details, see [README.md](README.md).
