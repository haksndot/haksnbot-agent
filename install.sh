#!/bin/bash
# Install Haksnbot Agent dependencies
# Usage: ./install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Haksnbot Agent Installation ==="

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"
if [[ $(echo "$PYTHON_VERSION < 3.10" | bc -l) -eq 1 ]]; then
    echo "Error: Python 3.10+ required"
    exit 1
fi

# Check that minecraft-mcp exists
if [ ! -f "$SCRIPT_DIR/../minecraft-mcp/src/index.js" ]; then
    echo "Error: minecraft-mcp not found at ../minecraft-mcp/"
    echo "Please ensure minecraft-mcp is installed first."
    exit 1
fi

# Check that chat-poll.sh exists
if [ ! -f "$SCRIPT_DIR/../chat-poll.sh" ]; then
    echo "Error: chat-poll.sh not found at ../chat-poll.sh"
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate venv and install Python deps
echo "Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create data directory
mkdir -p data

echo ""
echo "=== Installation complete ==="
echo ""
echo "To run the agent:"
echo "  cd $SCRIPT_DIR"
echo "  source venv/bin/activate"
echo "  python3 -m core"
echo ""
echo "Or simply: ./run.sh"
echo ""
echo "Note: The claude-agent-sdk package may require authentication."
echo "See https://github.com/anthropics/claude-agent-sdk-python for setup."
