#!/bin/bash
# FINAL COVERAGE REPORT - Solo módulos verificados
# Generado: 28 Dic 2025

echo "================================================================================"
echo "🎯 BACKEND COVERAGE FINAL - Módulos Verificados"
echo "================================================================================"
echo ""

echo "Ejecutando coverage en módulos principales..."
echo ""

# driver_scoring_engine - VERIFICADO 94.29%
echo "1️⃣  driver_scoring_engine..."
python -m pytest tests/test_driver_scoring.py tests/test_driver_scoring_integration.py \
    --cov=driver_scoring_engine --cov-report=term-missing:skip-covered -q 2>&1 | \
    grep "TOTAL" | tail -1

# alert_service - VERIFICADO 33.51%
echo "2️⃣  alert_service..."
python -m pytest tests/test_alert_service.py \
    --cov=alert_service --cov-report=term-missing:skip-covered -q 2>&1 | \
    grep "TOTAL" | tail -1

# database_mysql - VERIFICADO 4.94%
echo "3️⃣  database_mysql..."
python -m pytest tests/test_database_mysql_simple.py \
    --cov=database_mysql --cov-report=term-missing:skip-covered -q 2>&1 | \
    grep "TOTAL" | tail -1

# auth - Tests pasan pero no coverage data
echo "4️⃣  auth..."
python -m pytest tests/test_auth.py \
    --cov=auth --cov-report=term-missing:skip-covered -q 2>&1 | \
    grep -E "(TOTAL|passed)" | tail -2

# cache_service - Tests pasan pero no coverage data
echo "5️⃣  cache_service..."
python -m pytest tests/test_cache_service.py \
    --cov=cache_service --cov-report=term-missing:skip-covered -q 2>&1 | \
    grep -E "(TOTAL|passed)" | tail -2

echo ""
echo "================================================================================"
echo "📊 RESUMEN"
echo "================================================================================"
echo ""
echo "✅ driver_scoring_engine:  94.29%  (28 tests)  - EXCELENTE"
echo "⚠️  alert_service:          33.51%  (21 tests)  - NECESITA MEJORA"
echo "❌ database_mysql:           4.94%  (8 tests)   - NECESITA MEJORA"
echo "❓ auth:                     N/A    (21 tests)  - Sin coverage data"
echo "❓ cache_service:            N/A    (25 tests)  - Sin coverage data"
echo ""
echo "================================================================================"
echo "Total Ejecutado: 5 módulos principales en ~30 segundos"
echo "================================================================================"
