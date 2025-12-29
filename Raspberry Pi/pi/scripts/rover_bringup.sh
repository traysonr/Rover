#!/bin/bash
# Rover Bringup Script
# Starts all rover services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "========================================="
echo "Rover Bringup - Phase 1"
echo "========================================="

# Check if virtual environment exists
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv "$PROJECT_ROOT/venv"
    source "$PROJECT_ROOT/venv/bin/activate"
    pip install --upgrade pip
    pip install -r "$PROJECT_ROOT/requirements.txt"
else
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Check configuration
if [ ! -f "$PROJECT_ROOT/config/rover_config.yaml" ]; then
    echo "ERROR: Configuration file not found!"
    echo "Please create config/rover_config.yaml"
    exit 1
fi

# Export PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Start API server (includes all services)
echo ""
echo "Starting Rover Control API Server..."
echo "Access UI at: http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$PROJECT_ROOT/apps/api_server"
python api_server.py

