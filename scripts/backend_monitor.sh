#!/bin/bash

# Monitor daemon para el backend de Fuel Analytics
LOG_FILE="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/backend_monitor.log"
BACKEND_SCRIPT="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/start_backend_service.sh"

echo "$(date): Starting Fuel Analytics Backend Monitor" >> "$LOG_FILE"

while true; do
    # Verificar si el backend está corriendo
    if ! lsof -ti:8000 > /dev/null; then
        echo "$(date): Backend not running, starting..." >> "$LOG_FILE"
        
        # Cambiar al directorio correcto
        cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
        
        # Iniciar el backend en background
        bash "$BACKEND_SCRIPT" >> "$LOG_FILE" 2>&1 &
        
        # Esperar un poco para que inicie
        sleep 10
        
        # Verificar si inició correctamente
        if lsof -ti:8000 > /dev/null; then
            echo "$(date): Backend started successfully" >> "$LOG_FILE"
        else
            echo "$(date): Failed to start backend" >> "$LOG_FILE"
        fi
    else
        echo "$(date): Backend is running" >> "$LOG_FILE"
    fi
    
    # Esperar 30 segundos antes del siguiente check
    sleep 30
done