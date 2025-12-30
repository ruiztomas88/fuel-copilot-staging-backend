#!/bin/bash
###############################################################################
# STOP ALL FUEL COPILOT SERVICES
# Este script detiene todos los servicios del sistema
###############################################################################

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  STOPPING FUEL COPILOT SERVICES${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to stop a service
stop_service() {
    local service_name=$1
    local search_pattern=$2
    
    echo -e "${YELLOW}Stopping $service_name...${NC}"
    
    PIDS=$(pgrep -f "$search_pattern")
    
    if [ -z "$PIDS" ]; then
        echo -e "${YELLOW}⚠${NC}  $service_name not running"
        return 0
    fi
    
    for PID in $PIDS; do
        kill $PID
        echo -e "${GREEN}✓${NC} Stopped PID $PID"
    done
    
    # Wait for process to die
    sleep 2
    
    # Force kill if still running
    STILL_RUNNING=$(pgrep -f "$search_pattern")
    if [ ! -z "$STILL_RUNNING" ]; then
        echo -e "${RED}⚠${NC}  Force killing remaining processes..."
        for PID in $STILL_RUNNING; do
            kill -9 $PID
            echo -e "${GREEN}✓${NC} Force killed PID $PID"
        done
    fi
}

# Stop all services
stop_service "Wialon Sync" "wialon_sync_enhanced.py"
stop_service "FastAPI" "uvicorn.*main:app"
stop_service "Sensor Cache" "sensor_cache_updater.py"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  FINAL STATUS${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Verify all stopped
if ! pgrep -f "wialon_sync_enhanced.py\|uvicorn.*main:app\|sensor_cache_updater.py" > /dev/null; then
    echo -e "${GREEN}✓ All services stopped${NC}"
else
    echo -e "${RED}✗ Some services still running${NC}"
    echo ""
    echo "Running processes:"
    ps aux | grep -E "wialon_sync_enhanced|uvicorn.*main|sensor_cache_updater" | grep -v grep
fi

echo ""
