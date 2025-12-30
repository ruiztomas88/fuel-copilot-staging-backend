#!/bin/bash
# Script de Testing con Cobertura - Fuel Analytics Backend
# Generado: 28 de Diciembre 2025

echo "════════════════════════════════════════════════════════════════"
echo "🧪 EJECUTANDO SUITE DE TESTS CON COBERTURA"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para ejecutar tests por módulo
run_module_tests() {
    local module_name=$1
    local test_pattern=$2
    local coverage_module=$3
    
    echo -e "${YELLOW}📊 Testing: $module_name${NC}"
    /opt/anaconda3/bin/python -m pytest $test_pattern \
        --cov=$coverage_module \
        --cov-report=term-missing \
        --cov-report=html \
        --cov-append \
        -v -q \
        2>&1 | tail -20
    echo ""
}

# Limpiar coverage anterior
rm -f .coverage
rm -rf htmlcov/

echo "1️⃣ Predictive Maintenance Tests..."
run_module_tests "Predictive Maintenance" \
    "tests/test_predictive_maintenance.py tests/test_predictive_final_complete_90pct.py tests/test_predictive_ultra_specific_lines.py" \
    "predictive_maintenance_engine"

echo "2️⃣ Fleet Command Center Tests..."
run_module_tests "Fleet Command Center" \
    "tests/test_fleet_100_coverage.py tests/test_fleet_100_final.py tests/test_fleet_100pct_db.py" \
    "fleet_command_center"

echo "3️⃣ Fuel System Tests..."
run_module_tests "Fuel System" \
    "tests/test_fuel_estimator.py tests/test_fuel_event_classifier.py" \
    "fuel_estimator,fuel_event_classifier"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo -e "${GREEN}✅ TESTS COMPLETADOS${NC}"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📊 Ver reporte HTML: open htmlcov/index.html"
echo "📄 Ver reporte completo: cat TESTING_REPORT_DEC28_2025.md"
echo ""

# Generar resumen final
echo "📈 Resumen de Cobertura:"
/opt/anaconda3/bin/python -m coverage report --precision=2 | grep -E "predictive|fleet|fuel|TOTAL"
