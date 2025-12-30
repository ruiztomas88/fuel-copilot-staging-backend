#!/bin/bash
# Ultra-simple launcher for launchd
# Just set env and run Python - no loops, no complexity

# Change to backend directory explicitly
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend || exit 1

# Source .env manually
set -a
[ -f .env ] && . .env
set +a

# Run Python directly with full paths
export PATH=/opt/anaconda3/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/Users/tomasruiz/Desktop/Fuel-Analytics-Backend
export PYTHONUNBUFFERED=1
export DEV_MODE=false

# Use exec to replace shell with python process
exec /opt/anaconda3/bin/python /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/main.py
