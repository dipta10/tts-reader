#!/bin/bash

set -e  # Exit on error

echo "🔧 Setting up TTS Reader..."
echo ""

# Detect Python executable (prefer python3, fallback to python)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Error: Python is not installed or not in PATH."
    echo "   Please install Python 3.9 or higher and try again."
    exit 1
fi

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
PYTHON_MAJOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info[0])')
REQUIRED_VERSION="3.9"

# Ensure it's Python 3
if [ "$PYTHON_MAJOR" != "3" ]; then
    echo "❌ Error: Python 3.9 or higher is required."
    echo "   Detected: Python $PYTHON_VERSION (Python 2 is not supported)"
    echo "   Please install Python 3.9 or higher and try again."
    exit 1
fi

# Check minimum version
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Error: Python $REQUIRED_VERSION or higher is required."
    echo "   Your Python version: $PYTHON_VERSION"
    echo "   Please install Python $REQUIRED_VERSION or higher and try again."
    exit 1
fi

echo "✓ Python $PYTHON_VERSION detected (using $PYTHON_CMD)"
echo ""

# Check for required system dependencies
echo "Checking system dependencies..."
missing_deps=()

if ! command -v ffmpeg &> /dev/null; then
    missing_deps+=("ffmpeg")
fi

if ! command -v aplay &> /dev/null && [[ "$OSTYPE" == "linux-gnu"* ]]; then
    missing_deps+=("aplay (alsa-utils)")
fi

if [[ ${#missing_deps[@]} -gt 0 ]]; then
    echo "⚠️  Warning: The following system dependencies are missing:"
    for dep in "${missing_deps[@]}"; do
        echo "   - $dep"
    done
    echo ""
    echo "Please install them using your package manager before running the app."
    echo ""
fi

# Create virtual environment
if [ -d "venv" ]; then
    echo "Virtual environment already exists, skipping creation..."
else
    echo "Creating virtual environment with system-site-packages..."
    $PYTHON_CMD -m venv venv --system-site-packages
fi

# Activate virtual environment
case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*)
        VENV_ACTIVATE_PATH="venv/Scripts/activate"
        ;;
    *)
        VENV_ACTIVATE_PATH="venv/bin/activate"
        ;;
esac

echo "Activating virtual environment..."

# Check if the activation script exists before sourcing
if [ -f "$VENV_ACTIVATE_PATH" ]; then
    source "$VENV_ACTIVATE_PATH"
else
    echo "Error: Virtual environment activation script not found at $VENV_ACTIVATE_PATH"
fi
# Install main requirements
echo "Installing main dependencies..."
pip install -r requirements.txt

# Install Piper TTS dependencies
echo "Installing Piper TTS dependencies..."
pip install --no-deps -r piper.requirements.txt

# Create models directory
echo "Creating models directory..."
mkdir -p models

# Download Piper voice model
if [ -f "models/en_US-hfc_male-medium.onnx" ] && [ -f "models/en_US-hfc_male-medium.onnx.json" ]; then
    echo "Voice model already exists, skipping download..."
else
    echo "Downloading Piper voice model (en_US-hfc_male-medium)..."
    echo "This may take a moment..."

    MODEL_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_male/medium/en_US-hfc_male-medium.onnx?download=true"
    CONFIG_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_male/medium/en_US-hfc_male-medium.onnx.json?download=true"

    curl -L "$MODEL_URL" -o models/en_US-hfc_male-medium.onnx
    curl -L "$CONFIG_URL" -o models/en_US-hfc_male-medium.onnx.json
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run the application:"
echo "  1. Activate the virtual environment:"
echo "       source $VENV_ACTIVATE_PATH"
echo ""
echo "  2. Start the server:"
echo "       $PYTHON_CMD main.py --port 5000 --piper-model models/en_US-hfc_male-medium.onnx --piper-model-config models/en_US-hfc_male-medium.onnx.json"
echo ""
echo "  Or use the example from run_app.sh for more options"
echo ""
