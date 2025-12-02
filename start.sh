#!/bin/bash
# ============================================================================
# FUEL COPILOT BACKEND - LINUX/MAC STARTUP SCRIPT
# ============================================================================

echo "========================================"
echo "  FUEL COPILOT BACKEND"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "WARNING: .env file not found!"
    cp .env.example .env
    echo "Created .env from template. Please edit it with your settings."
fi

# Start the server
echo ""
echo "Starting Fuel Copilot API..."
echo ""
echo "API will be available at:"
echo "  - Local: http://localhost:8000/fuelanalytics/docs"
echo ""

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
