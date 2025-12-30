#!/bin/bash

echo "🔍 REFUEL SYSTEM HEALTH CHECK"
echo "======================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check 1: wialon_sync running
echo "1. Checking if wialon_sync is running..."
if ps aux | grep -q "wialon_sync_enhanced.py" | grep -v grep > /dev/null 2>&1; then
    echo -e "${GREEN}✅ wialon_sync is running${NC}"
else
    echo -e "${RED}❌ wialon_sync is NOT running${NC}"
    echo "   Starting wialon_sync..."
    cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
    nohup python3 wialon_sync_enhanced.py > logs/wialon_sync.log 2>&1 &
    sleep 3
    if ps aux | grep -q "wialon_sync_enhanced.py" | grep -v grep > /dev/null 2>&1; then
        echo -e "${GREEN}✅ wialon_sync restarted${NC}"
    else
        echo -e "${RED}❌ Failed to start wialon_sync${NC}"
    fi
fi

echo ""
echo "2. Checking recent refuel detection logs..."
tail -50 /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon_sync.log | grep -i "refuel\|REFUEL" | head -5
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠️  No recent refuel detections in logs${NC}"
fi

echo ""
echo "3. Checking database connectivity..."
mysql -u root fuel_copilot_local -e "SELECT COUNT(*) as refuel_count FROM refuel_events;" 2>&1 | tail -2

echo ""
echo "4. Last 3 refuels recorded in database:"
mysql -u root fuel_copilot_local -e "SELECT refuel_time, truck_id, before_pct, after_pct, gallons_added FROM refuel_events ORDER BY refuel_time DESC LIMIT 3;" 2>&1

echo ""
echo "======================================"
echo "🔧 Configuration:"
echo "   - wialon_sync log: /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon_sync.log"
echo "   - See REFUEL_ANALYSIS_DETAILED.md for troubleshooting"
echo ""
