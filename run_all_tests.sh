#!/bin/bash
# run_all_tests.sh - Comprehensive Testing Script
# This script runs ALL tests and generates complete coverage reports

set -e

echo "==============================================="
echo "🧪 FUEL ANALYTICS - COMPREHENSIVE TEST SUITE"
echo "==============================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to backend directory
cd "$(dirname "$0")"

echo "📦 Installing test dependencies..."
pip install -q pytest pytest-cov pytest-asyncio faker httpx

echo ""
echo "🧹 Cleaning previous test artifacts..."
rm -rf htmlcov coverage.json .coverage .pytest_cache
mkdir -p test_results

echo ""
echo "==============================================="
echo "🚀 PHASE 1: UNIT TESTS"
echo "==============================================="
echo ""

# Run unit tests with coverage
pytest tests/ \
    -v \
    --cov=src \
    --cov=main \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-report=json:coverage.json \
    --tb=short \
    -m "not slow" \
    | tee test_results/unit_tests.log

UNIT_RESULT=$?

echo ""
echo "==============================================="
echo "📊 PHASE 2: INTEGRATION TESTS"
echo "==============================================="
echo ""

# Run integration tests
pytest tests/ \
    -v \
    --tb=short \
    -m "integration or api" \
    | tee test_results/integration_tests.log

INTEGRATION_RESULT=$?

echo ""
echo "==============================================="
echo "📈 PHASE 3: COVERAGE ANALYSIS"
echo "==============================================="
echo ""

# Generate coverage summary
python3 << EOF
import json
import os

if os.path.exists('coverage.json'):
    with open('coverage.json', 'r') as f:
        cov_data = json.load(f)
    
    totals = cov_data.get('totals', {})
    percent_covered = totals.get('percent_covered', 0)
    
    print(f"\n📊 COVERAGE SUMMARY:")
    print(f"   Total Lines: {totals.get('num_statements', 0)}")
    print(f"   Covered Lines: {totals.get('covered_lines', 0)}")
    print(f"   Missing Lines: {totals.get('missing_lines', 0)}")
    print(f"   Coverage: {percent_covered:.2f}%\n")
    
    # Coverage by file
    files = cov_data.get('files', {})
    if files:
        print("\n📁 TOP 10 FILES BY COVERAGE:")
        sorted_files = sorted(files.items(), 
                            key=lambda x: x[1]['summary']['percent_covered'], 
                            reverse=True)[:10]
        for fname, fdata in sorted_files:
            fname_short = fname.split('/')[-1]
            pct = fdata['summary']['percent_covered']
            print(f"   {fname_short:40s} {pct:6.2f}%")
    
    # Save summary
    with open('test_results/coverage_summary.txt', 'w') as f:
        f.write(f"Coverage: {percent_covered:.2f}%\n")
        f.write(f"Total Lines: {totals.get('num_statements', 0)}\n")
        f.write(f"Covered: {totals.get('covered_lines', 0)}\n")
        f.write(f"Missing: {totals.get('missing_lines', 0)}\n")
else:
    print("⚠️  No coverage data found")
EOF

echo ""
echo "==============================================="
echo "📋 PHASE 4: TEST RESULTS SUMMARY"
echo "==============================================="
echo ""

# Count test results
TOTAL_TESTS=$(grep -E "passed|failed" test_results/unit_tests.log | tail -1 || echo "0 tests")
echo "Unit Tests: $TOTAL_TESTS"

INTEGRATION_TESTS=$(grep -E "passed|failed" test_results/integration_tests.log | tail -1 || echo "0 tests")
echo "Integration Tests: $INTEGRATION_TESTS"

echo ""
echo "==============================================="
echo "✅ TEST EXECUTION COMPLETE"
echo "==============================================="
echo ""

if [ $UNIT_RESULT -eq 0 ] && [ $INTEGRATION_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
    echo ""
    echo "📊 Coverage Report: htmlcov/index.html"
    echo "📁 Test Results: test_results/"
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    echo ""
    echo "Unit Tests Exit Code: $UNIT_RESULT"
    echo "Integration Tests Exit Code: $INTEGRATION_RESULT"
    echo ""
    echo "📊 Review logs in test_results/"
    exit 1
fi
