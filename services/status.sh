#!/bin/bash
# Script para ver el estado de todos los servicios Fuel Analytics

echo "════════════════════════════════════════════════════════════"
echo "  📊 ESTADO DE SERVICIOS FUEL ANALYTICS"
echo "════════════════════════════════════════════════════════════"
echo ""

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Función para verificar servicio
check_service() {
    local service_name=$1
    local port=$2
    
    echo -n "  $service_name: "
    
    # Verificar si el servicio está cargado
    if launchctl list | grep -q "com.fuelanalytics.$service_name"; then
        # Si tiene puerto, verificar que esté escuchando
        if [ -n "$port" ]; then
            if lsof -ti:$port > /dev/null 2>&1; then
                echo -e "${GREEN}✅ CORRIENDO (puerto $port)${NC}"
            else
                echo -e "${YELLOW}⚠️  CARGADO pero NO escuchando en puerto $port${NC}"
            fi
        else
            echo -e "${GREEN}✅ CORRIENDO${NC}"
        fi
    else
        echo -e "${RED}❌ NO ACTIVO${NC}"
    fi
}

# Verificar servicios
check_service "backend" "8000"
check_service "wialon" ""
check_service "frontend" "3000"

echo ""
echo "────────────────────────────────────────────────────────────"
echo "  🔍 PROCESOS LAUNCHD"
echo "────────────────────────────────────────────────────────────"
launchctl list | grep fuelanalytics | while read -r line; do
    echo "  $line"
done

echo ""
echo "────────────────────────────────────────────────────────────"
echo "  📁 ARCHIVOS DE CONFIGURACIÓN"
echo "────────────────────────────────────────────────────────────"
ls -lh ~/Library/LaunchAgents/com.fuelanalytics.*.plist 2>/dev/null | awk '{print "  " $9}' || echo "  No se encontraron archivos .plist"

echo ""
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Para ver logs en tiempo real:"
echo "  Backend:  tail -f ~/Desktop/Fuel-Analytics-Backend/logs/backend.log"
echo "  Wialon:   tail -f ~/Desktop/Fuel-Analytics-Backend/logs/wialon.log"
echo "  Frontend: tail -f ~/Desktop/Fuel-Analytics-Frontend/logs/frontend.log"
echo ""
