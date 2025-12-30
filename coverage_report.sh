#!/bin/bash
# Reporte rápido de coverage backend - ejecuta tests específicos por módulo
# Mucho más eficiente que pytest --cov=. que corre toda la noche

echo "================================================================================"
echo "📊 BACKEND COVERAGE REPORT - Fuel Analytics"
echo "================================================================================"
echo ""

# Función para ejecutar coverage de un módulo
run_coverage() {
    local module=$1
    local tests=$2
    local name=$3
    
    echo -n "Testing $name... "
    
    result=$(python -m pytest $tests --cov=$module --cov-report=term-missing:skip-covered -q --tb=no 2>&1 | grep "TOTAL" | tail -1)
    
    if [[ $result =~ ([0-9]+)% ]]; then
        pct="${BASH_REMATCH[1]}"
        printf "%-50s %6s%%\n" "$name" "$pct"
    else
        printf "%-50s %6s\n" "$name" "N/A"
    fi
}

# Módulos principales
run_coverage "auth" "tests/test_auth.py" "Authentication (auth.py)"
run_coverage "database_mysql" "tests/test_database_mysql*.py" "Database MySQL (database_mysql.py)"
run_coverage "cache_service" "tests/test_cache_service.py" "Cache Service (cache_service.py)"
run_coverage "alert_service" "tests/test_alert_service.py tests/test_alert_advanced.py" "Alert Service (alert_service.py)"
run_coverage "driver_scoring_engine" "tests/test_driver_scoring*.py" "Driver Scoring (driver_scoring_engine.py)"
run_coverage "mpg_engine" "tests/test_mpg_engine.py" "MPG Engine (mpg_engine.py)"
run_coverage "theft_detection_engine" "tests/test_siphon*.py tests/test_theft*.py" "Theft Detection (theft_detection_engine.py)"
run_coverage "predictive_maintenance_engine" "tests/test_predictive_maintenance*.py" "Predictive Maintenance (PM engine)"
run_coverage "driver_behavior_engine" "tests/test_driver_behavior*.py" "Driver Behavior (driver_behavior_engine.py)"
run_coverage "idle_engine" "tests/test_idle*.py" "Idle Time Engine (idle_engine.py)"
run_coverage "gamification_engine" "tests/test_gamification*.py" "Gamification (gamification_engine.py)"
run_coverage "api_middleware" "tests/test_api_middleware.py" "API Middleware (api_middleware.py)"
run_coverage "models" "tests/test_models*.py" "Models & Validation (models.py)"

echo ""
echo "================================================================================"
echo "✅ Coverage report completado en ~3-5 minutos"
echo "💡 Comando eficiente vs pytest --cov=. (overnight sin terminar)"
echo "================================================================================"
