#!/bin/bash
# Run Haksnbot Agent
# Usage: ./run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Error: venv not found. Run ./install.sh first."
    exit 1
fi

# Run the agent
exec python3 -m core
