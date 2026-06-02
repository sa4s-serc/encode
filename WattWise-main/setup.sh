#!/bin/bash

# Setup script for Energy Estimator VS Code Extension

set -e

echo "======================================"
echo "Energy Estimator Extension Setup"
echo "======================================"
echo ""

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Must run from extension root directory"
    exit 1
fi

# Check Python
echo "1. Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✓ Found Python $PYTHON_VERSION"

# Check Node.js
echo ""
echo "2. Checking Node.js installation..."
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+"
    exit 1
fi

NODE_VERSION=$(node --version)
echo "✓ Found Node.js $NODE_VERSION"

# Install Python dependencies
echo ""
echo "3. Installing Python dependencies..."
pip3 install --user pandas numpy scikit-learn xgboost joblib 2>&1 | grep -E "(Successfully installed|Requirement already satisfied)" || true
echo "✓ Python dependencies installed"

# Install Node dependencies
echo ""
echo "4. Installing Node.js dependencies..."
npm install
echo "✓ Node.js dependencies installed"

# Check for training data
echo ""
echo "5. Checking for training data..."
DATA_DIR="data"
mkdir -p "$DATA_DIR"

REQUIRED_FILES=("X_train_base_features.csv" "X_test_base_features.csv" "target_variables.csv")
MISSING_FILES=()

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$DATA_DIR/$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    echo "✓ All training data files found"
else
    echo "⚠️  Missing training data files:"
    for file in "${MISSING_FILES[@]}"; do
        echo "   - $file"
    done
    echo ""
    echo "Attempting to copy from parent directory..."

    PARENT_DIR=".."
    for file in "${MISSING_FILES[@]}"; do
        if [ -f "$PARENT_DIR/$file" ]; then
            cp "$PARENT_DIR/$file" "$DATA_DIR/"
            echo "   ✓ Copied $file"
        else
            echo "   ✗ $file not found in $PARENT_DIR"
        fi
    done
fi

# Train models
echo ""
echo "6. Training ML models..."
read -p "Train models now? This may take several minutes (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cd python
    python3 train_and_save_models.py
    cd ..

    if [ -d "python/models" ]; then
        echo "✓ Models trained successfully"
    else
        echo "❌ Model training failed"
        exit 1
    fi
else
    echo "⚠️  Skipped model training. Run manually: cd python && python3 train_and_save_models.py"
fi

# Compile TypeScript
echo ""
echo "7. Compiling TypeScript..."
npm run compile
echo "✓ TypeScript compiled"

# Final instructions
echo ""
echo "======================================"
echo "✅ Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Open this folder in VS Code"
echo "2. Press F5 to launch the extension in debug mode"
echo "3. Open a Python file in the new window"
echo "4. Right-click → 'Analyze Energy Consumption'"
echo ""
echo "Or to package for installation:"
echo "   npm install -g vsce"
echo "   vsce package"
echo "   code --install-extension energy-estimator-1.0.0.vsix"
echo ""
echo "Happy coding! 🔋"
