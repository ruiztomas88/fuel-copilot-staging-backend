#!/bin/bash

# Backend E2E Coverage Report - Real Data Testing
# Target: 90%+ coverage on main modules

echo "======================================"
echo "Backend E2E Testing - Real Database"
echo "======================================"
echo ""

echo "Testing alert_service..."
python -m pytest tests/test_alert_service.py tests/test_backend_comprehensive_e2e.py \
    --cov=alert_service \
    --cov-report=term-missing \
    -q --tb=no \
    | grep -E "(TOTAL|passed|failed)"

echo ""
echo "Testing database_mysql..."
python -m pytest tests/test_database_mysql_e2e.py tests/test_backend_comprehensive_e2e.py \
    --cov=database_mysql \
    --cov-report=term-missing \
    -q --tb=no \
    | grep -E "(TOTAL|passed|failed)"

echo ""
echo "Testing driver_scoring_engine..."
python -m pytest tests/test_driver_scoring_engine.py \
    --cov=driver_scoring_engine \
    --cov-report=term-missing \
    -q --tb=no \
    | grep -E "(TOTAL|passed|failed)"

echo ""
echo "======================================"
echo "Coverage Summary Complete"
echo "======================================"
