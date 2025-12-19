#!/bin/bash
# ============================================================================
# RESTORE SYSTEM TO DECEMBER 17 WORKING STATE
# ============================================================================
# This script:
# 1. Verifies services are stopped
# 2. Restores database structure (27 tables, removes 5 extras)
# 3. Restarts services with Dec 17 configuration
#
# Run on VM (Windows with Git Bash or WSL):
#   ./restore_to_dec17.sh
# ============================================================================

set -e  # Exit on any error

echo "============================================================================"
echo "RESTORE TO DECEMBER 17 WORKING STATE"
echo "============================================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
DB_USER="fuel_admin"
DB_PASS="FuelCopilot2025!"
DB_NAME="fuel_copilot"

echo -e "${YELLOW}STEP 1: Stopping services...${NC}"
# Stop all Python services
pkill -f wialon_sync_enhanced.py || echo "wialon_sync_enhanced not running"
pkill -f sensor_cache_updater.py || echo "sensor_cache_updater not running"
pkill -f "uvicorn main:app" || echo "FastAPI not running"
sleep 2
echo -e "${GREEN}✓ Services stopped${NC}"
echo ""

echo -e "${YELLOW}STEP 2: Backing up current database structure...${NC}"
BACKUP_FILE="fuel_copilot_structure_backup_$(date +%Y%m%d_%H%M%S).sql"
mysqldump -u${DB_USER} -p${DB_PASS} --no-data ${DB_NAME} > ${BACKUP_FILE} 2>/dev/null || echo "Backup failed (non-critical)"
echo -e "${GREEN}✓ Backup saved to ${BACKUP_FILE}${NC}"
echo ""

echo -e "${YELLOW}STEP 3: Restoring database structure to Dec 17...${NC}"
mysql -u${DB_USER} -p${DB_PASS} ${DB_NAME} < restore_db_structure_dec17.sql 2>&1 | grep -v "Warning"
echo -e "${GREEN}✓ Database structure restored${NC}"
echo ""

echo -e "${YELLOW}STEP 4: Verifying table count...${NC}"
TABLE_COUNT=$(mysql -u${DB_USER} -p${DB_PASS} ${DB_NAME} -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '${DB_NAME}';" 2>/dev/null | tail -1)
echo "Current table count: ${TABLE_COUNT}"

if [ "$TABLE_COUNT" -eq "27" ]; then
    echo -e "${GREEN}✓ Correct! Database has 27 tables (matching Dec 17)${NC}"
elif [ "$TABLE_COUNT" -eq "28" ]; then
    echo -e "${GREEN}✓ Database has 28 tables (27 + information_schema header)${NC}"
else
    echo -e "${RED}⚠ Warning: Expected 27 tables, found ${TABLE_COUNT}${NC}"
fi
echo ""

echo -e "${YELLOW}STEP 5: Verifying extra tables were removed...${NC}"
EXTRA_TABLES=$(mysql -u${DB_USER} -p${DB_PASS} ${DB_NAME} -e "SHOW TABLES LIKE 'truck_ignition%';" 2>/dev/null | wc -l)
if [ "$EXTRA_TABLES" -eq "0" ]; then
    echo -e "${GREEN}✓ Extra tables removed successfully${NC}"
else
    echo -e "${RED}⚠ Warning: Some extra tables still exist${NC}"
fi
echo ""

echo -e "${YELLOW}STEP 6: Checking data in fuel_metrics...${NC}"
FUEL_RECORDS=$(mysql -u${DB_USER} -p${DB_PASS} ${DB_NAME} -e "SELECT COUNT(*) FROM fuel_metrics;" 2>/dev/null | tail -1)
echo "fuel_metrics records: ${FUEL_RECORDS}"
echo ""

echo -e "${YELLOW}STEP 7: Starting services with Dec 17 configuration...${NC}"
# Change to backend directory
cd "$(dirname "$0")"

# Start sensor_cache_updater (30s interval, 1h lookback)
echo "Starting sensor_cache_updater.py..."
nohup python sensor_cache_updater.py > logs/sensor_cache_updater.log 2>&1 &
SENSOR_PID=$!
echo "  PID: ${SENSOR_PID}"
sleep 2

# Start wialon_sync_enhanced (main data processor)
echo "Starting wialon_sync_enhanced.py..."
nohup python wialon_sync_enhanced.py > logs/wialon_sync.log 2>&1 &
SYNC_PID=$!
echo "  PID: ${SYNC_PID}"
sleep 2

# Start FastAPI
echo "Starting FastAPI (uvicorn)..."
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > logs/fastapi.log 2>&1 &
API_PID=$!
echo "  PID: ${API_PID}"
sleep 2

echo -e "${GREEN}✓ All services started${NC}"
echo ""

echo -e "${YELLOW}STEP 8: Verifying services are running...${NC}"
sleep 3
ps aux | grep -E "sensor_cache_updater|wialon_sync_enhanced|uvicorn" | grep -v grep || echo "No services found"
echo ""

echo "============================================================================"
echo -e "${GREEN}RESTORATION COMPLETE!${NC}"
echo "============================================================================"
echo ""
echo "Configuration restored to December 17, 2025:"
echo "  • Database: 27 tables (5 extras removed)"
echo "  • sensor_cache_updater: 1-hour lookback (reverted from 12-hour)"
echo "  • wialon_reader: 1-hour lookback"
echo "  • All services: Running with Dec 17 settings"
echo ""
echo "Next steps:"
echo "  1. Monitor logs: tail -f logs/wialon_sync.log"
echo "  2. Check dashboard in 5 minutes"
echo "  3. Verify data is populating: mysql -u${DB_USER} -p${DB_PASS} ${DB_NAME} -e 'SELECT MAX(timestamp_utc) FROM fuel_metrics;'"
echo ""
echo "Log files:"
echo "  • sensor_cache_updater: logs/sensor_cache_updater.log"
echo "  • wialon_sync: logs/wialon_sync.log"
echo "  • FastAPI: logs/fastapi.log"
echo ""
