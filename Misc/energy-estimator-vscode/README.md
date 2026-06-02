# Python Energy Estimator - VS Code Extension

A VS Code extension that estimates energy consumption and classifies energy tiers for Python code blocks using machine learning models.

## Features

- 🔋 **Energy Estimation**: Predicts energy consumption in Joules for code blocks
- 📊 **Energy Tier Classification**: Categorizes blocks as Low/Medium/High energy
- 🎨 **Inline Decorations**: Shows estimates directly in your code
- 💡 **Hover Information**: Detailed energy metrics on hover
- 🤖 **ML-Powered**: Uses Gradient Boosting (regression) and XGBoost (classification)

## Supported Code Blocks

The extension analyzes the following Python code constructs:
- Functions (`def`)
- For loops
- While loops
- If statements
- Try-except blocks
- With statements

## Installation & Setup

### Prerequisites

1. **Python 3.8+** with the following packages:
   ```bash
   pip install pandas numpy scikit-learn xgboost lightgbm joblib
   ```

2. **Node.js 18+** and npm

3. **Training Data**: Place these CSV files in the `data/` directory:
   - `X_train_base_features.csv`
   - `X_test_base_features.csv`
   - `target_variables.csv`

### Setup Steps

1. **Clone/Copy the extension** to your workspace:
   ```bash
   cd /energy-estimator-vscode
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Copy your training data**:
   ```bash
   cp ../X_train_base_features.csv data/
   cp ../X_test_base_features.csv data/
   cp ../target_variables.csv data/
   ```

4. **Train the models** (one-time setup):
   ```bash
   cd python
   python3 train_and_save_models.py
   ```

   This will create a `models/` directory with:
   - `gradient_boosting_regressor.joblib` (energy prediction)
   - `xgboost_classifier.joblib` (tier classification)
   - `label_encoder.joblib` (label encoding)
   - `model_metadata.json` (feature names and boundaries)

5. **Compile TypeScript**:
   ```bash
   npm run compile
   ```

6. **Install the extension** in VS Code:
   - Press `F5` to open a new VS Code window with the extension loaded
   - Or package and install: `vsce package` then install the `.vsix` file

## Usage

### Analyzing a Python File

1. Open a Python file in VS Code
2. **Method 1**: Right-click → "Analyze Energy Consumption"
3. **Method 2**: Command Palette (`Ctrl+Shift+P`) → "Energy: Analyze Energy Consumption"
4. **Method 3**: Click the "⚡ Analyze Energy" button in the status bar

### Reading Results

**Inline Decorations** (shown at the end of each code block):
```python
def example_function():  # [Est: 1.23e-03J | Tier: Medium]
    for i in range(100):  # [Est: 5.67e-04J | Tier: Low]
        print(i)
```

**Hover Tooltips**: Hover over a code block to see:
- Block type
- Energy consumption (precise value)
- Energy tier (Low/Medium/High)
- Confidence score
- Recommendations

**Output Panel**: Detailed summary including:
- Total blocks analyzed
- Total and average energy
- Tier distribution
- Block-by-block breakdown
- Optimization recommendations

### Commands

- `Energy: Analyze Energy Consumption` - Analyze current Python file
- `Energy: Clear Energy Analysis` - Remove decorations
- `Energy: Train Energy Prediction Models` - Retrain models (if you update training data)

## Configuration

Open VS Code settings and search for "Energy Estimator":

```json
{
  "energyEstimator.pythonPath": "python3",
  "energyEstimator.showInlineDecorations": true,
  "energyEstimator.showHoverInfo": true,
  "energyEstimator.decorationFormat": "[Est: {energy}J | Tier: {tier}]"
}
```

## How It Works

### Pipeline

1. **Feature Extraction**:
   - Parses Python code using AST
   - Extracts 40+ static code metrics per block:
     - Cyclomatic complexity
     - Cognitive complexity
     - Halstead metrics
     - Node counts and depths
     - Operator/operand densities
     - Control flow complexity

2. **Preprocessing**:
   - Groups features by type (standard, robust, minmax, binary)
   - Applies appropriate scaling (StandardScaler, RobustScaler, MinMaxScaler)
   - Aligns features with training data

3. **Prediction**:
   - **Regression**: Gradient Boosting predicts energy in Joules
     - Uses sqrt transformation for better accuracy
     - Model params: `n_estimators=250, max_depth=6, learning_rate=0.06`
   - **Classification**: XGBoost predicts Low/Medium/High tier
     - Model params: `n_estimators=250, max_depth=6, learning_rate=0.08`
     - Provides confidence scores

4. **Visualization**:
   - Color-coded inline decorations (🟢🟡🔴)
   - Rich hover tooltips with detailed metrics
   - Summary report in Output panel

### Model Performance

From training:
- **Regression**: Test R² ≈ 0.81, Gap ≈ 0.05
- **Classification**: Test Accuracy ≈ 0.81, F1 ≈ 0.81

## Project Structure

```
energy-estimator-vscode/
├── src/
│   ├── extension.ts          # Main extension entry
│   ├── pythonBridge.ts       # Python script executor
│   └── decorations.ts        # UI decorations
├── python/
│   ├── train_and_save_models.py  # Model training script
│   ├── extract_features.py       # Feature extraction
│   ├── predict_energy.py         # Energy prediction
│   └── models/                   # Saved models (generated)
├── data/                      # Training data (user-provided)
├── package.json               # Extension manifest
├── tsconfig.json              # TypeScript config
└── README.md                  # This file
```

## Troubleshooting

### "Models not found" Error

**Solution**: Train models first:
```bash
cd python
python3 train_and_save_models.py
```

### "Feature extraction failed" Error

**Cause**: Python script failed to parse code

**Solutions**:
- Check Python syntax in your file
- Ensure Python interpreter is accessible
- Check `energyEstimator.pythonPath` setting

### Missing Dependencies

```bash
pip install pandas numpy scikit-learn xgboost joblib
```

### Extension Not Activating

- Check that file has `.py` extension
- Reload VS Code window: `Ctrl+Shift+P` → "Developer: Reload Window"
- Check console for errors: `Ctrl+Shift+P` → "Developer: Toggle Developer Tools"

## Development

### Running in Development Mode

1. Open the extension folder in VS Code
2. Press `F5` to start debugging
3. A new VS Code window opens with the extension loaded
4. Make changes, reload the debug window to test

### Building for Production

```bash
npm run compile
npm install -g vsce
vsce package
```

This creates a `.vsix` file you can install or distribute.

## Contributing

Contributions welcome! Areas for improvement:
- Support for more code block types
- Real-time analysis as you type
- Integration with CI/CD pipelines
- Energy optimization suggestions
- Support for other languages


---

**Note**: This tool provides **estimates** based on static code analysis. Actual energy consumption may vary based on:
- Hardware characteristics
- Runtime conditions
- Input data
- System load
- Compiler optimizations

For production energy profiling, combine with runtime measurement tools like RAPL, PyRAPL, or CodeCarbon.
