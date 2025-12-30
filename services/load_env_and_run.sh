#!/bin/bash
# Load .env and run backend
# This script properly sources .env before starting Python

cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend || exit 1

# Set base environment
export PATH=/opt/anaconda3/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
export PYTHONPATH=/Users/tomasruiz/Desktop/Fuel-Analytics-Backend
export PYTHONUNBUFFERED=1
export DEV_MODE=false

# Load .env file line by line (handles empty values correctly)
if [ -f .env ]; then
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        if [[ ! "$key" =~ ^#.* ]] && [ -n "$key" ]; then
            # Remove quotes if present
            value=$(echo "$value" | sed 's/^["'\'']\(.*\)["'\'']$/\1/')
            export "$key=$value"
        fi
    done < .env
fi

# Run backend
/opt/anaconda3/bin/python main.py
