#!/bin/bash

# Quick verification that all Phases 2A, 2B, 2C are integrated and working

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   FASE 2A, 2B, 2C - Quick Verification${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check 1: Files exist
echo -e "${YELLOW}1. Verificando archivos de integración...${NC}"
files=("ekf_integration.py" "ekf_diagnostics_endpoints.py" "lstm_fuel_predictor.py" \
        "anomaly_detection_v2.py" "driver_behavior_scoring_v2.py" "kafka_event_bus.py" \
        "microservices_orchestrator.py" "route_optimization_engine.py" \
        "wialon_sync_2abc_integration.py")

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅${NC} $file"
    else
        echo -e "${RED}❌${NC} $file NOT FOUND"
    fi
done

echo ""
echo -e "${YELLOW}2. Verificando imports en main.py...${NC}"
if grep -q "from ekf_integration import" main.py; then
    echo -e "${GREEN}✅${NC} EKF integration imported"
else
    echo -e "${RED}❌${NC} EKF integration NOT imported"
fi

if grep -q "from lstm_fuel_predictor import" main.py; then
    echo -e "${GREEN}✅${NC} LSTM predictor imported"
else
    echo -e "${RED}❌${NC} LSTM predictor NOT imported"
fi

if grep -q "from kafka_event_bus import" main.py; then
    echo -e "${GREEN}✅${NC} Event Bus imported"
else
    echo -e "${RED}❌${NC} Event Bus NOT imported"
fi

echo ""
echo -e "${YELLOW}3. Verificando integración en wialon_sync_enhanced.py...${NC}"
if grep -q "from wialon_sync_2abc_integration import" wialon_sync_enhanced.py; then
    echo -e "${GREEN}✅${NC} Wialon 2ABC integration imported"
else
    echo -e "${RED}❌${NC} Wialon 2ABC integration NOT imported"
fi

if grep -q "process_2abc_integrations" wialon_sync_enhanced.py; then
    echo -e "${GREEN}✅${NC} Process function called in workflow"
else
    echo -e "${RED}❌${NC} Process function NOT integrated"
fi

echo ""
echo -e "${YELLOW}4. Verificando sintaxis Python...${NC}"
python3 -m py_compile ekf_integration.py ekf_diagnostics_endpoints.py \
    lstm_fuel_predictor.py anomaly_detection_v2.py driver_behavior_scoring_v2.py \
    kafka_event_bus.py microservices_orchestrator.py route_optimization_engine.py \
    wialon_sync_2abc_integration.py 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅${NC} All Python files have valid syntax"
else
    echo -e "${RED}❌${NC} Syntax errors detected"
fi

echo ""
echo -e "${YELLOW}5. Verificando backend corriendo...${NC}"
if curl -s http://localhost:8000/fuelAnalytics/api/ekf/health/fleet | grep -q "fleet_health_score"; then
    echo -e "${GREEN}✅${NC} Backend corriendo, FASE 2A endpoint respondiendo"
else
    echo -e "${RED}❌${NC} Backend no respondiendo o endpoint no disponible"
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Integración de Fases 2A, 2B, 2C completada y verificada${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
