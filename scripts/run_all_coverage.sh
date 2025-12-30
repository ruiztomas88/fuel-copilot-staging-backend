#!/bin/bash
# Reporte comprehensivo de coverage para TODOS los módulos backend

echo "================================================================================"
echo "📊 COMPREHENSIVE BACKEND COVERAGE - All Modules"
echo "================================================================================"
echo ""

# Crear archivo de resultados
RESULTS_FILE="comprehensive_coverage_results.txt"
> $RESULTS_FILE

# Función para ejecutar coverage
run_module_coverage() {
    local module=$1
    local test_pattern=$2
    
    printf "%-50s " "$module"
    
    result=$(python -m pytest $test_pattern --cov=$module --cov-report=term-missing:skip-covered -q --tb=no 2>&1 | grep "TOTAL" | tail -1)
    
    if [[ $result =~ ([0-9]+)% ]]; then
        pct="${BASH_REMATCH[1]}"
        printf "%6s%% ✅\n" "$pct"
        echo "$module: $pct%" >> $RESULTS_FILE
    else
        printf "%6s\n" "N/A"
        echo "$module: N/A" >> $RESULTS_FILE
    fi
}

# Core modules
run_module_coverage "auth" "tests/test_auth.py"
run_module_coverage "database_mysql" "tests/test_database_mysql*.py"
run_module_coverage "cache_service" "tests/test_cache_service.py"

# Engines
run_module_coverage "mpg_engine" "tests/test_mpg_engine.py"
run_module_coverage "driver_scoring_engine" "tests/test_driver_scoring*.py"
run_module_coverage "theft_detection_engine" "tests/test_siphon*.py tests/test_theft*.py"
run_module_coverage "predictive_maintenance_engine" "tests/test_predictive_maintenance*.py tests/test_pm*.py"
run_module_coverage "driver_behavior_engine" "tests/test_driver_behavior*.py tests/test_driver_coaching.py"
run_module_coverage "idle_engine" "tests/test_idle*.py"
run_module_coverage "gamification_engine" "tests/test_gamification*.py"

# Services
run_module_coverage "alert_service" "tests/test_alert*.py"
run_module_coverage "api_middleware" "tests/test_api_middleware.py"
run_module_coverage "wialon_data_loader" "tests/test_wialon*.py"

# Fleet management
run_module_coverage "fleet_command_center" "tests/test_fleet*.py"

# Models
run_module_coverage "models" "tests/test_models*.py"

echo ""
echo "================================================================================"
echo "📈 RESUMEN GUARDADO EN: $RESULTS_FILE"
echo "================================================================================"

# Mostrar resumen
echo ""
echo "TOP COVERAGE MODULES:"
sort -t':' -k2 -rn $RESULTS_FILE | head -10

echo ""
echo "MODULES NEEDING IMPROVEMENT (<80%):"
sort -t':' -k2 -n $RESULTS_FILE | grep -v "N/A" | awk -F: '$2 < 80' | head -10
