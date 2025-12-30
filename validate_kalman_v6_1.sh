#!/bin/bash
# 🧪 Kalman v6.1.0 - Final Validation Script
# Verifica que todas las mejoras estén correctamente implementadas

echo "================================================================================"
echo "🧪 KALMAN FILTER v6.1.0 - VALIDATION SCRIPT"
echo "================================================================================"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

# Test 1: Import check
echo ""
echo "📝 Test 1: Import estimator.py..."
if python -c "from estimator import FuelEstimator" 2>/dev/null; then
    echo -e "${GREEN}✅ PASS${NC}: estimator.py imports successfully"
    ((PASSED++))
else
    echo -e "${RED}❌ FAIL${NC}: estimator.py has import errors"
    ((FAILED++))
fi

# Test 2: Check version
echo ""
echo "📝 Test 2: Verify version..."
VERSION=$(grep "^# Kalman Filter v" estimator.py | head -1 | grep -o "v[0-9]\+\.[0-9]\+\.[0-9]\+")
if [ "$VERSION" == "v6.1.0" ]; then
    echo -e "${GREEN}✅ PASS${NC}: Version is $VERSION"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠️  WARNING${NC}: Version is $VERSION (expected v6.1.0)"
fi

# Test 3: Check innovation_history exists
echo ""
echo "📝 Test 3: Check innovation_history attribute..."
if grep -q "self.innovation_history.*=.*deque" estimator.py; then
    echo -e "${GREEN}✅ PASS${NC}: innovation_history deque found"
    ((PASSED++))
else
    echo -e "${RED}❌ FAIL${NC}: innovation_history deque NOT found"
    ((FAILED++))
fi

# Test 4: Check bias_detected attribute
echo ""
echo "📝 Test 4: Check bias_detected attribute..."
if grep -q "self.bias_detected = False" estimator.py; then
    echo -e "${GREEN}✅ PASS${NC}: bias_detected attribute found"
    ((PASSED++))
else
    echo -e "${RED}❌ FAIL${NC}: bias_detected attribute NOT found"
    ((FAILED++))
fi

# Test 5: Check biodiesel_correction method
echo ""
echo "📝 Test 5: Check _get_biodiesel_correction method..."
if grep -q "def _get_biodiesel_correction" estimator.py; then
    echo -e "${GREEN}✅ PASS${NC}: _get_biodiesel_correction method found"
    ((PASSED++))
else
    echo -e "${RED}❌ FAIL${NC}: _get_biodiesel_correction method NOT found"
    ((FAILED++))
fi

# Test 6: Check _adaptive_measurement_noise_v2 method
echo ""
echo "📝 Test 6: Check _adaptive_measurement_noise_v2 method..."
if grep -q "def _adaptive_measurement_noise_v2" estimator.py; then
    echo -e "${GREEN}✅ PASS${NC}: _adaptive_measurement_noise_v2 method found"
    ((PASSED++))
else
    echo -e "${RED}❌ FAIL${NC}: _adaptive_measurement_noise_v2 method NOT found"
    ((FAILED++))
fi

# Test 7: Check get_estimate includes bias info
echo ""
echo "📝 Test 7: Check get_estimate returns bias info..."
if grep -q '"bias_detected"' estimator.py; then
    echo -e "${GREEN}✅ PASS${NC}: bias_detected in get_estimate output"
    ((PASSED++))
else
    echo -e "${RED}❌ FAIL${NC}: bias_detected NOT in get_estimate output"
    ((FAILED++))
fi

# Test 8: Run quick test suite
echo ""
echo "📝 Test 8: Run test_kalman_quick.py..."
if python test_kalman_quick.py --truck CO0681 2>&1 | grep -q "ALL TESTS PASSED"; then
    echo -e "${GREEN}✅ PASS${NC}: All quick tests passed"
    ((PASSED++))
else
    echo -e "${RED}❌ FAIL${NC}: Quick tests failed"
    ((FAILED++))
fi

# Test 9: Check backup exists
echo ""
echo "📝 Test 9: Check backup file exists..."
if [ -f "estimator.py.bak" ]; then
    echo -e "${GREEN}✅ PASS${NC}: Backup file exists (estimator.py.bak)"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠️  WARNING${NC}: No backup file found"
fi

# Test 10: Verify innovation tracking in update()
echo ""
echo "📝 Test 10: Verify innovation tracking..."
if grep -q "self.innovation_history.append" estimator.py; then
    echo -e "${GREEN}✅ PASS${NC}: Innovation tracking in update() method"
    ((PASSED++))
else
    echo -e "${RED}❌ FAIL${NC}: Innovation tracking NOT found in update()"
    ((FAILED++))
fi

# Summary
echo ""
echo "================================================================================"
echo "📊 VALIDATION SUMMARY"
echo "================================================================================"
echo -e "  Passed: ${GREEN}$PASSED${NC}"
echo -e "  Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL VALIDATIONS PASSED - Ready for deployment!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Test with real backend: python backend.py"
    echo "  2. Monitor bias_detected warnings in logs"
    echo "  3. Deploy to staging for 7-day observation"
    exit 0
else
    echo -e "${RED}❌ $FAILED validation(s) failed - Fix issues before deployment${NC}"
    exit 1
fi
