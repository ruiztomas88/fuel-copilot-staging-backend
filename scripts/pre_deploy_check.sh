#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
#                         PRE-DEPLOY CHECK SCRIPT
#                   Run this BEFORE pushing to production!
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage: ./pre_deploy_check.sh
#
# This script will:
# 1. Run critical startup tests (app imports, no duplicates)
# 2. Run full test suite
# 3. Check for syntax errors in all Python files
# 4. Verify no debug code left behind
#
# Exit codes:
#   0 = All checks passed, safe to deploy
#   1 = Tests failed, DO NOT DEPLOY
#   2 = Syntax errors found, DO NOT DEPLOY
# ═══════════════════════════════════════════════════════════════════════════════

set -e  # Exit on first error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║                         🚀 PRE-DEPLOY CHECK                                    ║"
echo "║                    Fuel Analytics Backend v5.0                                 ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Track failures
FAILURES=0

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Syntax Check
# ─────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}[1/5]${NC} Checking Python syntax..."

SYNTAX_ERRORS=$(find . -name "*.py" -not -path "./venv/*" -not -path "./.venv/*" -not -path "./__pycache__/*" -exec python3 -m py_compile {} \; 2>&1) || true

if [ -n "$SYNTAX_ERRORS" ]; then
    echo -e "${RED}❌ Syntax errors found:${NC}"
    echo "$SYNTAX_ERRORS"
    FAILURES=$((FAILURES + 1))
else
    echo -e "${GREEN}✅ No syntax errors${NC}"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Critical Startup Tests
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[2/5]${NC} Running critical startup tests..."

if python3 -m pytest tests/test_critical_startup.py -v --tb=short -q 2>&1; then
    echo -e "${GREEN}✅ Critical startup tests passed${NC}"
else
    echo -e "${RED}❌ Critical startup tests FAILED${NC}"
    FAILURES=$((FAILURES + 1))
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Full Test Suite (quick mode)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[3/5]${NC} Running full test suite..."

if python3 -m pytest tests/ --tb=no -q 2>&1 | tail -5; then
    RESULT=$(python3 -m pytest tests/ --tb=no -q 2>&1 | tail -1)
    if echo "$RESULT" | grep -q "failed"; then
        echo -e "${RED}❌ Some tests FAILED${NC}"
        FAILURES=$((FAILURES + 1))
    else
        echo -e "${GREEN}✅ All tests passed${NC}"
    fi
else
    echo -e "${RED}❌ Test suite FAILED${NC}"
    FAILURES=$((FAILURES + 1))
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Check for debug code
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[4/5]${NC} Checking for debug code..."

DEBUG_PATTERNS="print\(.*DEBUG|import pdb|pdb.set_trace|breakpoint\(\)|console.log.*DEBUG"
DEBUG_FOUND=$(grep -rn --include="*.py" -E "$DEBUG_PATTERNS" . --exclude-dir=venv --exclude-dir=.venv --exclude-dir=__pycache__ --exclude-dir=tests 2>/dev/null | head -10) || true

if [ -n "$DEBUG_FOUND" ]; then
    echo -e "${YELLOW}⚠️  Possible debug code found:${NC}"
    echo "$DEBUG_FOUND"
    echo "(This is a warning, not a failure)"
else
    echo -e "${GREEN}✅ No debug code found${NC}"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Check main.py can import
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[5/5]${NC} Verifying main.py imports..."

if python3 -c "import main; print(f'Routes: {len(main.app.routes)}')" 2>&1; then
    echo -e "${GREEN}✅ main.py imports successfully${NC}"
else
    echo -e "${RED}❌ main.py FAILED to import${NC}"
    FAILURES=$((FAILURES + 1))
fi

# ─────────────────────────────────────────────────────────────────────────────
# Final Result
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"

if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}"
    echo "  ✅ ALL CHECKS PASSED - Safe to deploy!"
    echo -e "${NC}"
    echo "═══════════════════════════════════════════════════════════════════════════════"
    exit 0
else
    echo -e "${RED}"
    echo "  ❌ $FAILURES CHECK(S) FAILED - DO NOT DEPLOY!"
    echo ""
    echo "  Fix the issues above before pushing to production."
    echo -e "${NC}"
    echo "═══════════════════════════════════════════════════════════════════════════════"
    exit 1
fi
