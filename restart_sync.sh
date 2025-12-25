#!/bin/bash

# Restart wialon_sync service
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend

# Kill any existing instances
pkill -f "wialon_sync_enhanced.py"
sleep 2

# Start the service
nohup python3 wialon_sync_enhanced.py > logs/wialon_sync.log 2>&1 &

echo "✅ wialon_sync restarted"
sleep 5

# Check if it's running
if ps aux | grep -q "wialon_sync_enhanced.py" | grep -v grep; then
    echo "✅ Service is running"
else
    echo "❌ Service failed to start"
    tail -20 logs/wialon_sync.log
fi
