#!/bin/bash
# Script para ver el estado de los servicios

echo "📊 Estado de servicios Fuel Analytics"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Función para obtener estado de un servicio
check_service() {
    local service=$1
    local name=$2
    
    if launchctl list | grep -q "$service"; then
        local pid=$(launchctl list | grep "$service" | awk '{print $1}')
        if [ "$pid" != "-" ]; then
            echo "✅ $name - Corriendo (PID: $pid)"
        else
            echo "⚠️  $name - Cargado pero no corriendo"
        fi
    else
        echo "❌ $name - No instalado"
    fi
}

check_service "com.fuelanalytics.backend" "Backend API"
check_service "com.fuelanalytics.wialon" "Wialon Sync"
check_service "com.fuelanalytics.frontend" "Frontend"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Logs recientes del backend:"
tail -n 5 /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/backend.log 2>/dev/null || echo "  (sin logs aún)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Comandos útiles:"
echo "  Ver logs en vivo:  tail -f ~/Desktop/Fuel-Analytics-Backend/logs/*.log"
echo "  Reiniciar todo:    bash services/restart_services.sh"
echo "  Detener todo:      bash services/stop_services.sh"
echo ""
