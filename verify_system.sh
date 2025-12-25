#!/bin/bash
# Quick System Verification Script
# Verifica que backend, frontend y BD funcionan correctamente

set -e

echo "================================================"
echo "🔍 FUEL ANALYTICS - SYSTEM VERIFICATION"
echo "================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ERRORS=0

# Function to check service
check_service() {
    SERVICE=$1
    URL=$2
    EXPECTED=$3
    
    echo -n "Checking $SERVICE... "
    
    RESPONSE=$(curl -s "$URL" 2>&1 || echo "CURL_ERROR")
    
    if echo "$RESPONSE" | grep -q "$EXPECTED"; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        echo "  Expected to find: $EXPECTED"
        echo "  Got: $(echo "$RESPONSE" | head -c 100)..."
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

# Function to check database
check_database() {
    echo -n "Checking MySQL database... "
    
    RESULT=$(python3 -c "
import pymysql
try:
    conn = pymysql.connect(host='localhost', user='root', password='', database='fuel_copilot_local')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM fuel_metrics LIMIT 1')
    count = cursor.fetchone()[0]
    conn.close()
    print('OK')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1)
    
    if echo "$RESULT" | grep -q "OK"; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        echo "  $RESULT"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

# Function to check process
check_process() {
    PROCESS_NAME=$1
    
    echo -n "Checking process '$PROCESS_NAME'... "
    
    if ps aux | grep -v grep | grep -q "$PROCESS_NAME"; then
        echo -e "${GREEN}✅ RUNNING${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  NOT RUNNING${NC}"
        return 1
    fi
}

# 1. Check Backend API
echo "1️⃣  Backend API (http://localhost:8000)"
check_service "Fleet API" "http://localhost:8000/fuelAnalytics/api/fleet" "total_trucks"
check_service "KPIs API" "http://localhost:8000/fuelAnalytics/api/kpis?days=7" "total_fuel"
check_service "Trucks List" "http://localhost:8000/fuelAnalytics/api/trucks" "CO0681"
echo ""

# 2. Check Frontend
echo "2️⃣  Frontend (http://localhost:3000)"
check_service "Frontend" "http://localhost:3000" "Fuel Copilot"
echo ""

# 3. Check Database
echo "3️⃣  MySQL Database"
check_database
echo ""

# 4. Check Background Processes
echo "4️⃣  Background Processes"
check_process "wialon_sync_enhanced.py" || echo "  (Warning: sync not running, data may be stale)"
check_process "vite" || echo "  (Warning: frontend dev server not running)"
echo ""

# 5. Check Architecture Files
echo "5️⃣  New Architecture Files (from commits 190h/245h)"
FILES=(
    "src/models/command_center_models.py"
    "src/orchestrators/fleet_orchestrator.py"
    "src/services/analytics_service.py"
    "src/repositories/truck_repository.py"
    "execute_production_deployment.sh"
    "load_j1939_database.sh"
    "COMMITS_190H_245H_IMPLEMENTATION.md"
)

for FILE in "${FILES[@]}"; do
    echo -n "  - $FILE... "
    if [ -f "$FILE" ]; then
        echo -e "${GREEN}✅ EXISTS${NC}"
    else
        echo -e "${RED}❌ MISSING${NC}"
        ERRORS=$((ERRORS + 1))
    fi
done
echo ""

# 6. Summary
echo "================================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"
    echo ""
    echo "System Status: HEALTHY"
    echo "Backend: http://localhost:8000"
    echo "Frontend: http://localhost:3000"
    echo ""
    echo "Next steps:"
    echo "  1. Review COMMITS_190H_245H_IMPLEMENTATION.md"
    echo "  2. Decide on migration plan (gradual vs big-bang)"
    echo "  3. Run tests: pytest tests/ -v"
    exit 0
else
    echo -e "${RED}❌ $ERRORS CHECK(S) FAILED${NC}"
    echo ""
    echo "Please fix the issues above before proceeding."
    exit 1
fi
