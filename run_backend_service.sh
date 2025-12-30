#!/bin/bash
# Backend API launcher - simplified for launchd
# launchd's KeepAlive handles auto-restart

cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend || exit 1

export PATH=/opt/anaconda3/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
export PYTHONPATH=/Users/tomasruiz/Desktop/Fuel-Analytics-Backend
export PYTHONUNBUFFERED=1
export DEV_MODE=false

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Just run once - launchd will restart if needed
exec /opt/anaconda3/bin/python main.py
