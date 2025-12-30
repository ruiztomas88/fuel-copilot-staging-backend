#!/bin/bash
###############################################################################
# START ALL FUEL COPILOT SERVICES
# Este script inicia todos los servicios necesarios para que el sistema funcione
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Base directory
BACKEND_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend"
LOG_DIR="$BACKEND_DIR/logs"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  FUEL COPILOT - SERVICE STARTER${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check if a service is running
check_service() {
    local service_name=$1
    local search_pattern=$2
    
    if pgrep -f "$search_pattern" > /dev/null; then
        echo -e "${GREEN}✓${NC} $service_name is running"
        return 0
    else
        echo -e "${RED}✗${NC} $service_name is NOT running"
        return 1
    fi
}

# Function to start a service
start_service() {
    local service_name=$1
    local script_name=$2
    local log_file=$3
    
    echo -e "\n${YELLOW}Starting $service_name...${NC}"
    
    cd "$BACKEND_DIR"
    nohup python "$script_name" > "$log_file" 2>&1 &
    local pid=$!
    
    sleep 2  # Wait for service to start
    
    if ps -p $pid > /dev/null; then
        echo -e "${GREEN}✓${NC} $service_name started (PID: $pid)"
        echo -e "   Log: $log_file"
        return 0
    else
        echo -e "${RED}✗${NC} Failed to start $service_name"
        echo -e "   Check log: $log_file"
        return 1
    fi
}

# Check current status
echo -e "${BLUE}Checking current service status...${NC}\n"

WIALON_RUNNING=false
API_RUNNING=false
SENSOR_CACHE_RUNNING=false

if check_service "Wialon Sync" "wialon_sync_enhanced.py"; then
    WIALON_RUNNING=true
fi

if check_service "FastAPI" "uvicorn.*main:app"; then
    API_RUNNING=true
fi

if check_service "Sensor Cache" "sensor_cache_updater.py"; then
    SENSOR_CACHE_RUNNING=true
fi

echo ""

# Start services if not running
STARTED_ANY=false

# 1. Wialon Sync (CRITICAL)
if [ "$WIALON_RUNNING" = false ]; then
    if start_service "Wialon Sync Service" "wialon_sync_enhanced.py" "$LOG_DIR/wialon_sync.log"; then
        STARTED_ANY=true
        echo -e "${YELLOW}⏳ Waiting 30 seconds for initial data collection...${NC}"
        sleep 30
    fi
else
    echo -e "\n${GREEN}✓${NC} Wialon Sync already running, skipping"
fi

# 2. FastAPI (CRITICAL)
if [ "$API_RUNNING" = false ]; then
    echo -e "\n${YELLOW}Starting FastAPI...${NC}"
    cd "$BACKEND_DIR"
    nohup uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2 > "$LOG_DIR/api.log" 2>&1 &
    API_PID=$!
    
    sleep 3
    
    if ps -p $API_PID > /dev/null; then
        echo -e "${GREEN}✓${NC} FastAPI started (PID: $API_PID)"
        echo -e "   Log: $LOG_DIR/api.log"
        echo -e "   URL: http://localhost:8000"
        STARTED_ANY=true
    else
        echo -e "${RED}✗${NC} Failed to start FastAPI"
        echo -e "   Check log: $LOG_DIR/api.log"
    fi
else
    echo -e "\n${GREEN}✓${NC} FastAPI already running, skipping"
fi

# 3. Sensor Cache (NICE TO HAVE)
if [ "$SENSOR_CACHE_RUNNING" = false ]; then
    if start_service "Sensor Cache Updater" "sensor_cache_updater.py" "$LOG_DIR/sensor_cache.log"; then
        STARTED_ANY=true
    fi
else
    echo -e "\n${GREEN}✓${NC} Sensor Cache already running, skipping"
fi

# Final status check
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  FINAL STATUS${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

check_service "Wialon Sync" "wialon_sync_enhanced.py"
check_service "FastAPI" "uvicorn.*main:app"
check_service "Sensor Cache" "sensor_cache_updater.py"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  VERIFICATION COMMANDS${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "View Wialon Sync logs:"
echo -e "  ${YELLOW}tail -f $LOG_DIR/wialon_sync.log${NC}"
echo ""
echo "View API logs:"
echo -e "  ${YELLOW}tail -f $LOG_DIR/api.log${NC}"
echo ""
echo "Test API endpoint:"
echo -e "  ${YELLOW}curl http://localhost:8000/fuelAnalytics/api/health | jq${NC}"
echo ""
echo "Check fuel_metrics table:"
echo -e "  ${YELLOW}mysql -ufuel_admin -p'FuelCopilot2025!' fuel_copilot -e \"SELECT truck_id, timestamp_utc, truck_status FROM fuel_metrics ORDER BY timestamp_utc DESC LIMIT 5;\"${NC}"
echo ""
echo "Stop all services:"
echo -e "  ${YELLOW}./stop_all_services.sh${NC}"
echo ""

if [ "$STARTED_ANY" = true ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Services started successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}  All services were already running${NC}"
    echo -e "${YELLOW}========================================${NC}"
fi

echo ""
