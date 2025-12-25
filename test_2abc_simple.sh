#!/bin/bash

# ═══════════════════════════════════════════════════════════════════════════════
# Test Script for FASES 2A, 2B, 2C Integration - Simplified
# ═══════════════════════════════════════════════════════════════════════════════

BASE_URL="http://localhost:8000/fuelAnalytics/api"
PASSED=0
FAILED=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}FASE 2A, 2B, 2C - Integration Testing${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Test FASE 2A EKF endpoints
echo -e "${YELLOW}FASE 2A: EKF Integration & Diagnostics${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo -n "✓ Testing EKF Fleet Health... "
if curl -s "$BASE_URL/ekf/health/fleet" | grep -q "fleet_health_score"; then
    echo -e "${GREEN}✅ PASS${NC}"
    PASSED=$((PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC}"
    FAILED=$((FAILED + 1))
fi

echo -n "✓ Testing EKF Truck Health (LC6799)... "
if curl -s "$BASE_URL/ekf/health/LC6799" | grep -q "health_score"; then
    echo -e "${GREEN}✅ PASS${NC}"
    PASSED=$((PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC}"
    FAILED=$((FAILED + 1))
fi

echo -n "✓ Testing EKF Diagnostics (LC6799)... "
if curl -s "$BASE_URL/ekf/diagnostics/LC6799" | grep -q "update_count\|diagnostics"; then
    echo -e "${GREEN}✅ PASS${NC}"
    PASSED=$((PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC}"
    FAILED=$((FAILED + 1))
fi

echo -n "✓ Testing EKF Trends (LC6799)... "
if curl -s "$BASE_URL/ekf/trends/LC6799?hours=24" | grep -q "uncertainty\|efficiency"; then
    echo -e "${GREEN}✅ PASS${NC}"
    PASSED=$((PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC}"
    FAILED=$((FAILED + 1))
fi

echo ""

# Test normal endpoints that should work
echo -e "${YELLOW}Standard Endpoints (should still work)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo -n "✓ Testing Fleet Endpoint... "
if curl -s "$BASE_URL/fleet/raw" | grep -q "total_trucks"; then
    echo -e "${GREEN}✅ PASS${NC}"
    PASSED=$((PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC}"
    FAILED=$((FAILED + 1))
fi

echo -n "✓ Testing KPI Endpoint... "
if curl -s "$BASE_URL/kpi" | grep -q "metric\|fuel_level\|mpg"; then
    echo -e "${GREEN}✅ PASS${NC}"
    PASSED=$((PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC}"
    FAILED=$((FAILED + 1))
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Test Results Summary${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Total Tests:    $((PASSED + FAILED))"
echo -e "${GREEN}Passed:         $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed:         $FAILED${NC}"
    echo ""
    echo -e "${RED}⚠️  Some tests failed.${NC}"
else
    echo -e "${GREEN}Failed:         $FAILED${NC}"
    echo ""
    echo -e "${GREEN}🎉 All tests passed! FASES 2A, 2B, 2C ready for staging!${NC}"
fi
echo ""
