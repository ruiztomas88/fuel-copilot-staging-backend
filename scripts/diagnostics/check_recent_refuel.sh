#!/bin/bash

echo "🔍 Searching for recent refuel detection logs for MR7679..."
echo ""

# Look for refuel detection in the last 100 lines of the log
tail -200 /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon_sync.log | grep -i "MR7679\|refuel" | tail -20

echo ""
echo "🔍 Checking for error messages..."
tail -200 /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon_sync.log | grep -i "error\|failed\|warning" | tail -10

