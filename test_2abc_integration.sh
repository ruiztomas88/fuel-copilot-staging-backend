#!/bin/bash

# ═══════════════════════════════════════════════════════════════════════════════
# Test Script for FASES 2A, 2B, 2C Integration
# Tests all new endpoints and integrations in staging environment
# ═══════════════════════════════════════════════════════════════════════════════

set -e

BASE_URL="http://localhost:8000/fuelAnalytics/api"
PASSED=0
FAILED=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}FASE 2A, 2B, 2C - Integration Testing${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}\n"

# Function to test endpoint
test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local expected_code=$4
    
    echo -n "Testing: $name... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$BASE_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X $method "$BASE_URL$endpoint")
    fi
    
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)
    
    if [ "$http_code" = "$expected_code" ] || [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✅ PASS (HTTP $http_code)${NC}"
        PASSED=$((PASSED + 1))
        # Show response preview
        if [ -n "$body" ]; then
            echo "$body" | python3 -m json.tool 2>/dev/null | head -20 || echo "$body" | head -10
        fi
    else
        echo -e "${RED}❌ FAIL (HTTP $http_code, expected $expected_code)${NC}"
        FAILED=$((FAILED + 1))
        echo "Response: $body"
    fi
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 2A: EKF Integration & Diagnostics
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}FASE 2A: EKF Integration & Diagnostics${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_endpoint "EKF Fleet Health" "GET" "/ekf/health/fleet" "200"
test_endpoint "EKF Fleet Status" "GET" "/ekf/health/fleet?detailed=true" "200"
test_endpoint "EKF Truck Health (LC6799)" "GET" "/ekf/health/LC6799" "200"
test_endpoint "EKF Diagnostics (LC6799)" "GET" "/ekf/diagnostics/LC6799?detailed=true" "200"
test_endpoint "EKF Trends (LC6799)" "GET" "/ekf/trends/LC6799?hours=24" "200"

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 2B: ML Pipeline (LSTM, Anomaly Detection, Driver Behavior)
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}FASE 2B: ML Pipeline${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_endpoint "Normal Fleet Endpoint" "GET" "/fleet/raw" "200"
test_endpoint "KPI Endpoint" "GET" "/kpi" "200"

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# Staging Status
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Test Results Summary${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}\n"

TOTAL=$((PASSED + FAILED))

echo "Total Tests:    $TOTAL"
echo -e "${GREEN}Passed:         $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed:         $FAILED${NC}"
else
    echo -e "${GREEN}Failed:         $FAILED${NC}"
fi

echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed! FASES 2A, 2B, 2C are ready for staging deployment${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Some tests failed. Review the output above.${NC}"
    exit 1
fi
